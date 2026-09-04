import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

pytestmark = pytest.mark.unit

OWNER = "12345"


def make_mock_update(is_owner=True, text=None, with_photo=False):
    """Mock Update/Context mirroring the existing studio test style.
    Plain media attributes are falsy unless with_photo; chat_data is a real
    dict so session state behaves like the bot's."""
    mock_user = MagicMock()
    mock_user.username = "tester"
    mock_user.first_name = "Test"

    mock_chat = MagicMock()
    mock_chat.id = OWNER if is_owner else "99999"

    mock_message = MagicMock()
    mock_message.chat = mock_chat
    mock_message.from_user = mock_user
    mock_message.message_id = 1
    mock_message.text = text
    mock_message.caption = None
    mock_message.video = None
    mock_message.audio = None
    mock_message.voice = None
    mock_message.document = None
    mock_message.photo = None
    mock_message.reply_text = AsyncMock()
    mock_message.reply_photo = AsyncMock()
    mock_message.reply_media_group = AsyncMock()
    if with_photo:
        file_obj = MagicMock()
        file_obj.download_to_drive = AsyncMock()
        mock_photo = MagicMock()
        mock_photo.get_file = AsyncMock(return_value=file_obj)
        mock_message.photo = [mock_photo]

    mock_update = MagicMock()
    mock_update.effective_chat = mock_chat
    mock_update.effective_user = mock_user
    mock_update.message = mock_message

    mock_context = MagicMock()
    mock_context.args = []
    mock_context.chat_data = {}

    return mock_update, mock_context


def import_bot():
    import scripts.elina_studio_bot as bot_module
    return bot_module


def import_cs():
    import agents.studio.carousel_session as cs
    return cs


def make_fake_plan_result(n_slides=3):
    from agents.carousel.schema import CarouselSlide
    from agents.carousel.deck_renderer import CarouselDeck
    from agents.carousel.planner import CarouselPlanResult

    slides = [CarouselSlide(slide_type="cover", title="کاور")]
    for i in range(n_slides - 2):
        slides.append(CarouselSlide(slide_type="quote", title=f"نقل {i + 1}"))
    slides.append(CarouselSlide(slide_type="cta", title="ذخیره کن"))
    deck = CarouselDeck(title="دک تست", template="psychological_dark", slides=slides)
    return CarouselPlanResult(
        deck=deck, caption="کپشن تست", hashtags=["#تست"], provider_used="groq"
    )


def make_fake_renderer(tmp_path):
    def render_deck(deck, output_dir):
        os.makedirs(output_dir, exist_ok=True)
        actual = []
        for i, s in enumerate(deck.slides):
            p = os.path.join(output_dir, f"{i + 1:02d}_{s.slide_type}.png")
            with open(p, "wb") as f:
                f.write(b"PNGDATA")
            actual.append(p)
        return actual

    r = MagicMock()
    r.render_deck = render_deck
    return r


def write_image(tmp_path, name, data=b"JPGDATA"):
    p = tmp_path / name
    p.write_bytes(data)
    return str(p)


# === A. /carousel starts session, shows mode menu (owner only) ===

@pytest.mark.asyncio
async def test_A_carousel_starts_session_with_menu():
    bot = import_bot()
    update, context = make_mock_update(is_owner=True)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel(update, context)
    reply = update.message.reply_text.call_args[0][0]
    assert "۱) عکس و متن می‌دهم" in reply
    assert "۲) عکس می‌دهم + موضوع" in reply
    assert "۳) فقط موضوع" in reply
    session = context.chat_data["carousel_session"]
    assert session["state"] == import_cs().MODE_SELECT


# === B. non-owner /carousel is rejected ===

@pytest.mark.asyncio
async def test_B_non_owner_rejected():
    bot = import_bot()
    update, context = make_mock_update(is_owner=False)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel(update, context)
    reply = update.message.reply_text.call_args[0][0]
    assert "⛔" in reply
    assert "carousel_session" not in context.chat_data


# === C. mode "1" selection transitions to COLLECT_IMAGES ===

@pytest.mark.asyncio
async def test_C_mode_1_to_collect_images():
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel(update, context)
        text_update, _ = make_mock_update(is_owner=True, text="1")
        await bot.handle_studio_media(text_update, context)
    reply = text_update.message.reply_text.call_args[0][0]
    assert "عکس‌ها را" in reply
    session = context.chat_data["carousel_session"]
    assert session["mode"] == "text_overlay"
    assert session["state"] == cs.COLLECT_IMAGES


# === D. Persian digit "۲" works for mode selection ===

def test_D_persian_digit_mode():
    cs = import_cs()
    session = cs.new_session()
    reply = cs.select_mode(session, "۲")
    assert session["mode"] == "image_deck"
    assert session["state"] == cs.COLLECT_IMAGES
    assert "عکس" in reply
    cs.cleanup(session)


# === E. photos collected in order; /done with <2 images -> error ===

@pytest.mark.asyncio
async def test_E_photo_collection_and_done_min(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel(update, context)
        await bot.handle_studio_media(make_mock_update(is_owner=True, text="1")[0], context)

        # one photo arrives
        photo_update, _ = make_mock_update(is_owner=True, with_photo=True)
        # make download write a real file
        local = write_image(tmp_path, "incoming.jpg")
        photo_update.message.photo[0].get_file.return_value.download_to_drive.side_effect = \
            lambda p: os.system(f"cp {local} {p}")
        await bot.handle_studio_media(photo_update, context)
        session = context.chat_data["carousel_session"]
        assert len(session["images"]) == 1
        assert os.path.exists(session["images"][0])

        # /done with 1 image -> Persian error
        done_update, _ = make_mock_update(is_owner=True)
        done_update.message = update.message
        await bot.cmd_done(done_update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "حداقل 2 عکس" in reply or "حداقل" in reply

        # second photo, order preserved
        photo2, _ = make_mock_update(is_owner=True, with_photo=True)
        local2 = write_image(tmp_path, "incoming2.jpg")
        photo2.message.photo[0].get_file.return_value.download_to_drive.side_effect = \
            lambda p: os.system(f"cp {local2} {p}")
        await bot.handle_studio_media(photo2, context)
        assert len(session["images"]) == 2
        assert "img_00" in os.path.basename(session["images"][0])
        assert "img_01" in os.path.basename(session["images"][1])
    cs.cleanup(context.chat_data["carousel_session"])


# === F. text_overlay: mismatched text count -> clear Persian error ===

@pytest.mark.asyncio
async def test_F_text_count_mismatch_error(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel(update, context)
        await bot.handle_studio_media(make_mock_update(is_owner=True, text="1")[0], context)
        for name in ("a.jpg", "b.jpg"):
            photo, _ = make_mock_update(is_owner=True, with_photo=True)
            local = write_image(tmp_path, name)
            photo.message.photo[0].get_file.return_value.download_to_drive.side_effect = \
                lambda p, l=local: os.system(f"cp {l} {p}")
            await bot.handle_studio_media(photo, context)
        done_update, _ = make_mock_update(is_owner=True)
        done_update.message = update.message
        await bot.cmd_done(done_update, context)
        assert context.chat_data["carousel_session"]["state"] == cs.COLLECT_TEXTS

        # only ONE text, but two images
        await bot.handle_studio_media(make_mock_update(is_owner=True, text="متن اول")[0], context)
        done2, _ = make_mock_update(is_owner=True)
        done2.message = update.message
        await bot.cmd_done(done2, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "تعداد متن (1) با تعداد عکس (2)" in reply
    cs.cleanup(context.chat_data["carousel_session"])


# === G. "title | body" parsing ===

def test_G_title_body_parsing():
    cs = import_cs()
    assert cs.parse_slide_text("عنوان | بدنه") == {"title": "عنوان", "body": "بدنه"}
    assert cs.parse_slide_text("فقط عنوان") == {"title": "فقط عنوان", "body": ""}
    assert cs.parse_slide_text("ع | ب | دو") == {"title": "ع", "body": "ب | دو"}  # first |
    session = cs.new_session()
    cs.add_text(session, "عنوان یک | بدنه یک")
    assert session["texts"] == [{"title": "عنوان یک", "body": "بدنه یک"}]
    cs.cleanup(session)


# === H. text_overlay build: planner called with mode, NO LLM ===

def test_H_text_overlay_build_calls_planner_without_llm(tmp_path):
    cs = import_cs()
    session = cs.new_session()
    assert cs.select_mode(session, "1") is not None
    img1 = write_image(tmp_path, "a.jpg")
    img2 = write_image(tmp_path, "b.jpg")
    assert cs.add_image(session, img1) is None
    assert cs.add_image(session, img2) is None
    assert cs.finish_images(session) is not None
    cs.add_text(session, "عنوان یک | بدنه")
    cs.add_text(session, "عنوان دو")
    assert cs.finish_texts(session) is None

    planner = MagicMock()
    planner.plan.return_value = make_fake_plan_result(2)
    renderer = make_fake_renderer(tmp_path)

    error = cs.build_deck(session, planner=planner, renderer=renderer)
    assert error is None
    kwargs = planner.plan.call_args[1]
    assert kwargs["mode"] == "text_overlay"
    assert len(kwargs["image_paths"]) == 2
    assert len(kwargs["slide_texts"]) == 2
    assert kwargs["slide_texts"][0] == {"title": "عنوان یک", "body": "بدنه"}
    # exactly one plan call; the mocked planner never touches an LLM
    assert planner.plan.call_count == 1
    assert session["state"] == cs.PREVIEW
    assert len(session["slide_paths"]) == 2
    assert session["caption"] == "کپشن تست"
    cs.cleanup(session)


# === I. image_deck: planner called with topic + image_paths ===

def test_I_image_deck_planner_args(tmp_path):
    cs = import_cs()
    session = cs.new_session()
    cs.select_mode(session, "2")
    for name in ("a.jpg", "b.jpg", "c.jpg"):
        assert cs.add_image(session, write_image(tmp_path, name)) is None
    assert cs.finish_images(session) is not None
    assert cs.set_topic(session, "موضوع تست") is None

    planner = MagicMock()
    planner.plan.return_value = make_fake_plan_result(3)
    renderer = make_fake_renderer(tmp_path)
    error = cs.build_deck(session, planner=planner, renderer=renderer)
    assert error is None
    kwargs = planner.plan.call_args[1]
    assert kwargs["mode"] == "image_deck"
    assert kwargs["topic"] == "موضوع تست"
    assert len(kwargs["image_paths"]) == 3
    assert session["state"] == cs.PREVIEW
    cs.cleanup(session)


# === J. ai_planned: planner called with character_asset_provider ===

def test_J_ai_planned_passes_character_provider(tmp_path):
    cs = import_cs()
    session = cs.new_session()
    assert cs.select_mode(session, "3") is not None
    assert cs.set_topic(session, "موضوع | ۴") is None
    assert session["slide_count"] == 4

    planner = MagicMock()
    planner.plan.return_value = make_fake_plan_result(4)
    renderer = make_fake_renderer(tmp_path)
    provider = MagicMock()
    error = cs.build_deck(session, planner=planner, renderer=renderer,
                          character_provider=provider)
    assert error is None
    args, kwargs = planner.plan.call_args
    assert args[0] == "موضوع"
    assert kwargs["slide_count"] == 4
    assert kwargs["character_asset_provider"] is provider
    cs.cleanup(session)


# === K. planner typed errors -> Persian message + recoverable state ===

def test_K_planner_errors_recoverable(tmp_path):
    from agents.carousel.planner import (
        CarouselPlanConfigError,
        CarouselPlanGenerationError,
    )
    cs = import_cs()

    # ai_planned generation failure -> back to COLLECT_TOPIC
    session = cs.new_session()
    cs.select_mode(session, "3")
    planner = MagicMock()
    planner.plan.side_effect = CarouselPlanGenerationError("no provider available")
    error = cs.build_deck(session, planner=planner, renderer=make_fake_renderer(tmp_path))
    assert error is not None
    assert "❌" in error
    assert "موضوع را دوباره بفرست" in error
    assert session["state"] == cs.COLLECT_TOPIC  # recoverable

    # text_overlay config failure -> back to COLLECT_TEXTS, texts cleared
    session2 = cs.new_session()
    cs.select_mode(session2, "1")
    cs.add_image(session2, write_image(tmp_path, "x.jpg"))
    cs.add_image(session2, write_image(tmp_path, "y.jpg"))
    cs.finish_images(session2)
    cs.add_text(session2, "متن")
    planner2 = MagicMock()
    planner2.plan.side_effect = CarouselPlanConfigError("slide_texts mismatch")
    error2 = cs.build_deck(session2, planner=planner2, renderer=make_fake_renderer(tmp_path))
    assert error2 is not None
    assert "❌" in error2
    assert session2["state"] == cs.COLLECT_TEXTS
    assert session2["texts"] == []  # cleared for re-entry
    assert len(session2["images"]) == 2  # images preserved
    cs.cleanup(session)
    cs.cleanup(session2)


# === L. preview sends media group with ordered slides ===

@pytest.mark.asyncio
async def test_L_preview_media_group_ordered(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, _ = make_mock_update(is_owner=True)
    session = cs.new_session()
    p1 = write_image(tmp_path, "s1.png", b"ONE")
    p2 = write_image(tmp_path, "s2.png", b"TWO")
    session["slide_paths"] = [p1, p2]
    session["state"] = cs.PREVIEW
    await bot._send_carousel_preview(update, session)
    update.message.reply_media_group.assert_called_once()
    media = update.message.reply_media_group.call_args[1]["media"]
    assert len(media) == 2
    cs.cleanup(session)


# === M. /carousel_edit 2 | new text updates slide 2 ===

@pytest.mark.asyncio
async def test_M_carousel_edit_updates_slide(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = cs.new_session()
    session["state"] = cs.PREVIEW
    deck = make_fake_plan_result(3)
    session["deck"] = deck.deck
    paths = [write_image(tmp_path, f"s{i}.png") for i in range(3)]
    session["slide_paths"] = paths
    fake_slide_renderer = MagicMock()

    def fake_render(slide, path):
        with open(path, "wb") as f:
            f.write(b"RENDERED")

    fake_slide_renderer.render = fake_render
    renderer = MagicMock()
    renderer.slide_renderer = fake_slide_renderer
    session["_renderer"] = renderer
    context.chat_data["carousel_session"] = session

    update.message.text = "/carousel_edit ۲ | متن جدید"
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_edit(update, context)

    assert deck.deck.slides[1].title == "متن جدید"
    update.message.reply_photo.assert_called_once()
    assert os.path.getsize(paths[1]) > 0
    # body replaced too when type supports it (slide 2 is quote -> title only)
    cs.cleanup(session)


# === N. /carousel_theme invalid -> error; valid -> re-render ===

@pytest.mark.asyncio
async def test_N_carousel_theme(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = cs.new_session()
    session["state"] = cs.PREVIEW
    session["deck"] = make_fake_plan_result(2).deck
    session["slide_paths"] = [write_image(tmp_path, "a.png"), write_image(tmp_path, "b.png")]
    renderer = MagicMock()
    session["_renderer"] = renderer
    context.chat_data["carousel_session"] = session

    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        # invalid template
        update.message.text = "/carousel_theme neon_pink"
        context.args = ["neon_pink"]
        await bot.cmd_carousel_theme(update, context)
        reply = update.message.reply_text.call_args[0][0]
        assert "معتبر نیست" in reply
        assert renderer.slide_renderer.render.call_count == 0

        # valid template -> whole deck re-rendered (2 slides)
        context.args = ["warm_cream"]
        await bot.cmd_carousel_theme(update, context)
        assert session["deck"].template == "warm_cream"
        assert renderer.slide_renderer.render.call_count == 2
        update.message.reply_media_group.assert_called_once()
    cs.cleanup(session)


# === O. /carousel_ok -> ordered upload + content item + session cleared ===

@pytest.mark.asyncio
async def test_O_carousel_ok_finalizes(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = cs.new_session()
    session["state"] = cs.PREVIEW
    session["deck"] = make_fake_plan_result(2).deck
    session["deck_title"] = "دک تست"
    session["caption"] = "کپشن"
    paths = [write_image(tmp_path, "a.png"), write_image(tmp_path, "b.png")]
    session["slide_paths"] = paths
    context.chat_data["carousel_session"] = session

    uploads = []

    class FakeStorage:
        def upload_file(self, local, dest, content_type=None):
            uploads.append((local, dest, content_type))
            return True

    def fake_upload(paths, cid, storage):
        keys = []
        for p in paths:
            key = f"carousel/{cid}/{os.path.basename(p)}"
            storage.upload_file(p, key, content_type="image/png")
            keys.append(key)
        return keys

    fake_renderer = MagicMock()
    fake_renderer.upload_deck_to_storage = fake_upload
    session["_renderer"] = fake_renderer

    inserted = []

    class FakeDB:
        def insert_content(self, data):
            inserted.append(data)
            return [data]

    with patch.object(bot, "OWNER_CHAT_ID", OWNER), \
         patch("agents.storage.supabase_storage.ElinaStorage", return_value=FakeStorage()), \
         patch("agents.db.supabase_client.ElinaDB", return_value=FakeDB()):
        await bot.cmd_carousel_ok(update, context)

    # ordered uploads with the deterministic prefix
    assert len(uploads) == 2
    cid = uploads[0][1].split("/")[1]
    assert cid.startswith("ELN-CAR-")
    assert uploads[0][1] == f"carousel/{cid}/{os.path.basename(paths[0])}"
    assert uploads[1][1] == f"carousel/{cid}/{os.path.basename(paths[1])}"
    assert uploads[0][0] == paths[0]
    assert uploads[0][2] == "image/png"
    # content item: carousel type + ordered media_keys + caption + status
    assert len(inserted) == 1
    payload = inserted[0]
    assert payload["content_type"] == "carousel"
    assert payload["custom_id"] == cid
    assert payload["media_keys"] == [u[1] for u in uploads]
    assert payload["caption_fa"] == "کپشن"
    assert payload["status"] == "READY_FOR_REVIEW"
    # session cleared + temp dir cleaned
    assert context.chat_data["carousel_session"] is None
    assert session["work_dir"] is None
    # final confirmation edited onto the "⏳" message
    final = update.message.reply_text.return_value.edit_text.call_args[0][0]
    assert cid in final
    assert "/promote" in final


# === P. /carousel_cancel clears session ===

@pytest.mark.asyncio
async def test_P_carousel_cancel_clears_session():
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel(update, context)
    session = context.chat_data["carousel_session"]
    work_dir = session["work_dir"]
    assert os.path.isdir(work_dir)
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_cancel(update, context)
    assert context.chat_data["carousel_session"] is None
    assert not os.path.isdir(work_dir)
    reply = update.message.reply_text.call_args[0][0]
    assert "لغو" in reply


# === Q. REGRESSION: photo with no carousel session follows old intake ===

@pytest.mark.asyncio
async def test_Q_photo_without_session_goes_to_intake(tmp_path):
    bot = import_bot()
    update, context = make_mock_update(is_owner=True, with_photo=True)
    context.chat_data = {}  # no carousel session

    local = write_image(tmp_path, "incoming.jpg")
    update.message.photo[0].get_file.return_value.download_to_drive.side_effect = \
        lambda p: os.system(f"cp {local} {p}")

    fake_result = {"custom_id": "ELN-RAW-TEST", "ok": True}
    with patch("agents.intake.telegram_intake.IntakeProcessor") as MockProcessor:
        MockProcessor.return_value.process_incoming_media.return_value = fake_result
        with patch.object(bot, "OWNER_CHAT_ID", OWNER):
            await bot.handle_studio_media(update, context)

    MockProcessor.assert_called_once()
    MockProcessor.return_value.process_incoming_media.assert_called_once()
    reply = update.message.reply_text.call_args[0][0]
    assert "✅ فایل وارد استودیو شد" in reply
    assert "ELN-RAW-TEST" in reply


# === R. REGRESSION: /plan flow works when no carousel session exists ===

@pytest.mark.asyncio
async def test_R_plan_flow_unchanged_without_carousel_session():
    bot = import_bot()
    update, context = make_mock_update(is_owner=True, text="شات اول از صفر تا ۲.۸")
    context.chat_data = {"plan_mode": True, "plan_target_id": "ELN-BUNDLE-X"}

    mock_plan = MagicMock()
    mock_plan.validate.return_value = []
    mock_interpreter = MagicMock()
    mock_interpreter.parse.return_value = mock_plan

    with patch.object(bot, "PersianEditInterpreter", return_value=mock_interpreter), \
         patch.object(bot, "format_plan_preview_fa", return_value="پیش‌نمایش برنامه ادیت"), \
         patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)

    assert context.chat_data["plan_preview"] is mock_plan
    reply = update.message.reply_text.call_args[0][0]
    assert "پیش‌نمایش برنامه ادیت" in reply
    assert "/plan_ok" in reply


# === M23 — /carousel_layout + /carousel_edit layout=|zone= tokens ===

def make_image_text_plan_result(n_slides=3):
    """A plan result whose non-cover content slides are image_text (so the
    layout/zone commands have targets)."""
    from agents.carousel.schema import CarouselSlide
    from agents.carousel.deck_renderer import CarouselDeck
    from agents.carousel.planner import CarouselPlanResult

    slides = [CarouselSlide(slide_type="cover", title="کاور")]
    for i in range(n_slides - 2):
        slides.append(CarouselSlide(slide_type="image_text",
                                    title=f"تصویر {i + 1}",
                                    image_path=f"/img/{i}.jpg",
                                    image_layout="auto"))
    slides.append(CarouselSlide(slide_type="cta", title="ذخیره کن"))
    deck = CarouselDeck(title="دک تصویری", template="psychological_dark", slides=slides)
    return CarouselPlanResult(deck=deck, caption="کپشن", hashtags=["#تست"],
                              provider_used=None)


def make_preview_session(tmp_path, n_slides=3, image_text=True):
    """A PREVIEW-state session with a real deck + renderer mocks, ready for
    layout/zone edits."""
    cs = import_cs()
    session = cs.new_session()
    session["state"] = cs.PREVIEW
    factory = make_image_text_plan_result if image_text else make_fake_plan_result
    session["deck"] = factory(n_slides).deck
    session["slide_paths"] = [write_image(tmp_path, f"s{i}.png") for i in range(n_slides)]
    def _fake_render(slide, path):
        with open(path, "wb") as f:
            f.write(b"RENDERED")

    fake_slide_renderer = MagicMock()
    fake_slide_renderer.render = MagicMock(side_effect=_fake_render)
    renderer = MagicMock()
    renderer.slide_renderer = fake_slide_renderer
    session["_renderer"] = renderer
    return session


# --- J. /carousel_layout <layout> applies to ALL non-cover image slides ---

def test_J_carousel_layout_all_non_cover_image_slides(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)  # cover + 2 img + cta
    deck = session["deck"]
    reply = cs.apply_layout(session, "contain")
    assert "✅" in reply
    # All non-cover image slides switched; cover/cta untouched
    for s in deck.slides:
        if s.slide_type == "image_text":
            assert s.image_layout == "contain_caption"
        else:
            assert s.image_layout is None
    # Each affected slide re-rendered once
    assert session["_renderer"].slide_renderer.render.call_count == 2
    cs.cleanup(session)


# --- K. /carousel_layout <layout> <n> applies to slide n only ---

def test_K_carousel_layout_single_slide(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    reply = cs.apply_layout(session, "full 2")
    assert "✅" in reply
    assert deck.slides[1].image_layout == "full_bleed_caption"
    # sibling image slide untouched
    assert deck.slides[2].image_layout == "auto"
    assert session["_renderer"].slide_renderer.render.call_count == 1
    cs.cleanup(session)


def test_K2_carousel_layout_persian_digit_and_out_of_range(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    assert "✅" in cs.apply_layout(session, "split ۲")
    assert deck.slides[1].image_layout == "split_panel"
    # out-of-range -> Persian error, nothing changed, no render
    before = session["_renderer"].slide_renderer.render.call_count
    err = cs.apply_layout(session, "full 99")
    assert "❌" in err
    assert session["_renderer"].slide_renderer.render.call_count == before
    cs.cleanup(session)


# --- L. /carousel_edit <n> | zone=... and layout=... tokens ---

def test_L_carousel_edit_zone_token(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    err, path = cs.edit_slide(session, 2, "zone=top")
    assert err is None and path is not None
    assert deck.slides[1].text_zone == "top"
    # re-rendered once
    assert session["_renderer"].slide_renderer.render.call_count == 1
    cs.cleanup(session)


def test_L2_carousel_edit_layout_token(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    err, path = cs.edit_slide(session, 2, "layout=contain")
    assert err is None and path is not None
    assert deck.slides[1].image_layout == "contain_caption"
    assert session["_renderer"].slide_renderer.render.call_count == 1
    cs.cleanup(session)


def test_L3_carousel_edit_invalid_zone_and_layout(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    # invalid zone -> Persian error, field unchanged, no render
    err, _ = cs.edit_slide(session, 2, "zone=nowhere")
    assert "❌" in err
    assert deck.slides[1].text_zone is None
    # invalid layout -> Persian error, field unchanged, no render
    err2, _ = cs.edit_slide(session, 2, "layout=poster")
    assert "❌" in err2
    assert deck.slides[1].image_layout == "auto"
    assert session["_renderer"].slide_renderer.render.call_count == 0
    # plain title|body editing still works
    err3, _ = cs.edit_slide(session, 2, "عنوان جدید | بدنه جدید")
    assert err3 is None
    assert deck.slides[1].title == "عنوان جدید"
    assert deck.slides[1].body == "بدنه جدید"
    cs.cleanup(session)


# --- M. invalid layout name -> Persian error, state preserved ---

def test_M_carousel_layout_invalid_name_preserves_state(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    before = [(s.image_layout, s.text_zone) for s in deck.slides]
    reply = cs.apply_layout(session, "poster")
    assert "❌" in reply
    assert "نام layout نامعتبر" in reply
    # state preserved (still PREVIEW), no layouts changed, no renders
    assert session["state"] == cs.PREVIEW
    assert [(s.image_layout, s.text_zone) for s in deck.slides] == before
    assert session["_renderer"].slide_renderer.render.call_count == 0
    # wrong state (COLLECT with a slide number -> stored, not applied)
    collect = cs.new_session()
    cs.select_mode(collect, "1")
    collect["state"] = cs.COLLECT_TEXTS
    r = cs.apply_layout(collect, "full")
    assert "✅" in r and "ذخیره" in r
    assert collect["pending_image_layout"] == "full_bleed_caption"
    cs.cleanup(session)
    cs.cleanup(collect)


# === M25 — composition tokens (zone/title_zone/body_zone/style/size) ===

def test_m25_edit_zone_persian_alias(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    err, path = cs.edit_slide(session, 2, "zone=بالا-راست")
    assert err is None and path is not None
    assert deck.slides[1].text_zone == "top_right"
    assert session["_renderer"].slide_renderer.render.call_count == 1
    cs.cleanup(session)


def test_m25_edit_split_zones(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    assert cs.edit_slide(session, 2, "title_zone=بالا")[0] is None
    assert cs.edit_slide(session, 2, "body_zone=پایین")[0] is None
    assert deck.slides[1].title_zone == "top"
    assert deck.slides[1].body_zone == "bottom"
    cs.cleanup(session)


def test_m25_edit_style_and_size(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    assert cs.edit_slide(session, 2, "style=blend")[0] is None
    assert deck.slides[1].text_style == "blend"
    assert cs.edit_slide(session, 2, "size=0.85")[0] is None
    assert deck.slides[1].text_scale == 0.85
    # Invalid values: Persian error, field unchanged, state preserved
    err, _ = cs.edit_slide(session, 2, "style=glow")
    assert "❌" in err and deck.slides[1].text_style == "blend"
    err2, _ = cs.edit_slide(session, 2, "size=5")
    assert "❌" in err2 and deck.slides[1].text_scale == 0.85
    err3, _ = cs.edit_slide(session, 2, "zone=هرجا")
    assert "❌" in err3 and deck.slides[1].text_zone is None
    assert session["state"] == cs.PREVIEW
    cs.cleanup(session)


def test_m25_layout_command_style_size_zone(tmp_path):
    """/carousel_layout style|size|zone forms apply to all photo slides
    (cover + image_text), or one slide with a number."""
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)  # cover + 2 img + cta
    deck = session["deck"]
    reply = cs.apply_layout(session, "style blend")
    assert "✅" in reply
    for i in (0, 1, 2):
        assert deck.slides[i].text_style == "blend"
    assert deck.slides[3].text_style is None  # cta untouched
    assert session["_renderer"].slide_renderer.render.call_count == 3

    reply2 = cs.apply_layout(session, "zone bottom_right 2")
    assert "✅" in reply2
    assert deck.slides[1].text_zone == "bottom_right"
    assert deck.slides[0].text_zone is None  # only slide 2

    reply3 = cs.apply_layout(session, "size 0.8")
    assert "✅" in reply3
    for i in (0, 1, 2):
        assert deck.slides[i].text_scale == 0.8
    assert deck.slides[3].text_scale is None

    # Persian zone alias + per-slide number
    reply4 = cs.apply_layout(session, "zone پایین-راست 3")
    assert "✅" in reply4
    assert deck.slides[2].text_zone == "bottom_right"
    assert deck.slides[1].text_zone == "bottom_right"
    cs.cleanup(session)


def test_m25_layout_command_invalid_preserves_state(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    before = [(s.text_style, s.text_scale, s.text_zone) for s in deck.slides]
    for raw in ("zone هرجا", "style glow", "size 9", "size abc", "mystery full"):
        reply = cs.apply_layout(session, raw)
        assert "❌" in reply, raw
    assert [(s.text_style, s.text_scale, s.text_zone) for s in deck.slides] == before
    assert session["state"] == cs.PREVIEW
    assert session["_renderer"].slide_renderer.render.call_count == 0
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_m25_bot_carousel_edit_zone_token(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = make_preview_session(tmp_path, n_slides=4)
    context.chat_data["carousel_session"] = session
    update.message.text = "/carousel_edit ۲ | zone=بالا"
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_edit(update, context)
    assert session["deck"].slides[1].text_zone == "top"
    update.message.reply_photo.assert_called_once()
    cs.cleanup(session)


# === M27A — title/body split must ignore pipes inside inline markup ===
#
# M26 markup uses '|' inside [...] brackets; the "title | body" input
# convention also uses '|'. The session must split only on pipes OUTSIDE
# brackets so marked-up text is not corrupted.

def test_M27A_parse_title_with_markup_and_body():
    cs = import_cs()
    r = cs.parse_slide_text("عنوان [خوب|color=#B89B65] | بدنه")
    assert r == {"title": "عنوان [خوب|color=#B89B65]", "body": "بدنه"}


def test_M27A_parse_body_with_markup():
    cs = import_cs()
    r = cs.parse_slide_text("عنوان ساده | بدنه [زنده|size=1.2] است")
    assert r == {"title": "عنوان ساده", "body": "بدنه [زنده|size=1.2] است"}


def test_M27A_parse_both_with_markup():
    cs = import_cs()
    r = cs.parse_slide_text("عنوان [a|c1] و [b|c2] | بدنه [c|c3]")
    assert r["title"] == "عنوان [a|c1] و [b|c2]"
    assert r["body"] == "بدنه [c|c3]"


def test_M27A_parse_plain_unchanged_regression():
    cs = import_cs()
    # Existing plain behavior is unchanged (first outside-pipe splits)
    assert cs.parse_slide_text("عنوان | بدنه") == {"title": "عنوان", "body": "بدنه"}
    assert cs.parse_slide_text("فقط عنوان") == {"title": "فقط عنوان", "body": ""}
    assert cs.parse_slide_text("ع | ب | دو") == {"title": "ع", "body": "ب | دو"}


def test_M27A_parse_malformed_brackets_no_crash():
    cs = import_cs()
    # Unclosed bracket -> falls back to a plain split; no crash
    r = cs.parse_slide_text("عنوان [بدون بستن | بدنه")
    assert r["title"] == "عنوان [بدون بستن"
    assert r["body"] == "بدنه"
    # Stray closing bracket -> plain split; no crash
    r2 = cs.parse_slide_text("عنوان ] بدن | ب")
    assert r2["title"] == "عنوان ] بدن"
    assert r2["body"] == "ب"


def test_M27A_edit_title_body_with_markup(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)  # cover + 2 img + cta
    deck = session["deck"]
    err, path = cs.edit_slide(session, 3, "وقتی [کلمه|color=#B89B65] بود | بدنه جدید")
    assert err is None
    # Markup kept intact in the title, body split correctly
    assert deck.slides[2].title == "وقتی [کلمه|color=#B89B65] بود"
    assert deck.slides[2].body == "بدنه جدید"
    cs.cleanup(session)


def test_M27A_edit_title_only_markup_no_body(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    err, path = cs.edit_slide(session, 3, "عنوان [خوب|color=#B89B65] بود")
    assert err is None
    assert deck.slides[2].title == "عنوان [خوب|color=#B89B65] بود"
    cs.cleanup(session)


def test_M27A_edit_body_with_markup(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    err, path = cs.edit_slide(session, 3, "عنوان ساده | بدنه [زنده|size=1.2] است")
    assert err is None
    assert deck.slides[2].title == "عنوان ساده"
    assert deck.slides[2].body == "بدنه [زنده|size=1.2] است"
    cs.cleanup(session)


def test_M27A_edit_zone_token_still_works_regression(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    # zone= token is detected before title|body parsing and still works
    err, path = cs.edit_slide(session, 3, "zone=top")
    assert err is None
    assert deck.slides[2].text_zone == "top"
    cs.cleanup(session)


def test_M27A_edit_malformed_brackets_no_crash(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    # Unclosed bracket -> plain split; no crash, sane title/body
    err, path = cs.edit_slide(session, 3, "عنوان [بدون بستن | بدنه")
    assert err is None
    assert deck.slides[2].title == "عنوان [بدون بستن"
    assert deck.slides[2].body == "بدنه"
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M27A_bot_edit_markup_title_body(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = make_preview_session(tmp_path, n_slides=4)
    context.chat_data["carousel_session"] = session
    update.message.text = "/carousel_edit ۳ | وقتی [کلمه|color=#B89B65] بود | بدنه جدید"
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_edit(update, context)
    # Slide 3 (slides[2]) updated with intact markup + split body
    assert session["deck"].slides[2].title == "وقتی [کلمه|color=#B89B65] بود"
    assert session["deck"].slides[2].body == "بدنه جدید"
    update.message.reply_photo.assert_called_once()
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M27A_bot_edit_zone_token_regression(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = make_preview_session(tmp_path, n_slides=4)
    context.chat_data["carousel_session"] = session
    update.message.text = "/carousel_edit ۳ | zone=top"
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_edit(update, context)
    assert session["deck"].slides[2].text_zone == "top"
    update.message.reply_photo.assert_called_once()
    cs.cleanup(session)


# === M27B — text_scale default override ===

def test_M27B_text_scale_default_and_override(tmp_path):
    cs = import_cs()
    session = make_preview_session(tmp_path, n_slides=4)
    deck = session["deck"]
    # Planner default for text_overlay decks (M27B): photo slides only
    for i in (0, 1, 2):
        deck.slides[i].text_scale = 0.85
    assert deck.slides[3].text_scale is None  # cta not set by the planner
    # User override per slide via /carousel_edit size=
    err, path = cs.edit_slide(session, 2, "size=1.0")
    assert err is None
    assert deck.slides[1].text_scale == 1.0
    # Other slides keep the default
    assert deck.slides[2].text_scale == 0.85
    # ...and deck-wide via /carousel_layout size=
    reply = cs.apply_layout(session, "size 1.3")
    assert "✅" in reply
    for i in (0, 1, 2):  # photo slides (cover + image_text)
        assert deck.slides[i].text_scale == 1.3
    assert deck.slides[3].text_scale is None  # cta untouched
    cs.cleanup(session)
