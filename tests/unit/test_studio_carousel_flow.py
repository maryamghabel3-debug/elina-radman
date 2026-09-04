import os
import time
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


# === M29: persistent draft, resume, reply re-register ===

class FakeDraftDB:
    """In-memory stand-in for the carousel_drafts Supabase table.

    `received_chat_ids` records every owner_chat_id received by any
    method so tests can assert the query never sees None / "None" (M29A).
    """

    def __init__(self):
        self.drafts = {}
        self.deleted = []
        self.received_chat_ids = []

    def upsert_carousel_draft(self, owner_chat_id, draft):
        self.received_chat_ids.append(owner_chat_id)
        record = {
            "id": "uuid-1",
            "owner_chat_id": owner_chat_id,
            "title": draft.get("title") or "",
            "custom_id": draft.get("custom_id"),
            "status": draft.get("status") or "draft",
            "draft": {k: v for k, v in draft.items()
                      if k not in ("title", "custom_id", "status")},
            "updated_at": "2026-09-04T00:00:00+00:00",
        }
        self.drafts[owner_chat_id] = record
        return [record]

    def get_carousel_draft(self, owner_chat_id):
        self.received_chat_ids.append(owner_chat_id)
        return self.drafts.get(owner_chat_id)

    def list_carousel_drafts(self, limit=10):
        return sorted(self.drafts.values(),
                      key=lambda r: r["updated_at"], reverse=True)[:limit]

    def delete_carousel_draft(self, owner_chat_id):
        self.received_chat_ids.append(owner_chat_id)
        self.deleted.append(owner_chat_id)
        self.drafts.pop(owner_chat_id, None)
        return []


class FakeMediaStorage:
    """In-memory stand-in for Supabase storage (upload/download bytes)."""

    def __init__(self):
        self.files = {}
        self.uploads = 0
        self.downloads = 0

    def upload_file(self, local, dest, content_type=None):
        with open(local, "rb") as f:
            self.files[dest] = f.read()
        self.uploads += 1
        return True

    def download_file(self, storage_path, local_path):
        data = self.files[storage_path]
        os.makedirs(os.path.dirname(local_path) or ".", exist_ok=True)
        with open(local_path, "wb") as f:
            f.write(data)
        self.downloads += 1
        return local_path


class FakeItemDB:
    def __init__(self):
        self.inserted = []

    def insert_content(self, data):
        self.inserted.append(data)
        return [data]


def _build_persisted_preview(tmp_path, db, storage, chat_id=12345,
                             tag=""):
    """Drive a text_overlay session to PREVIEW with persistence attached.
    Returns the session (deck slide image paths point at real temp files)."""
    cs = import_cs()
    session = cs.new_session()
    cs.attach_persistence(session, db, storage, chat_id)
    assert cs.select_mode(session, "1") is not None
    img1 = write_image(tmp_path, f"a{tag}.jpg", b"IMG1")
    img2 = write_image(tmp_path, f"b{tag}.jpg", b"IMG2")
    assert cs.add_image(session, img1) is None
    assert cs.add_image(session, img2) is None
    assert cs.finish_images(session) is not None
    cs.add_text(session, "عنوان یک | بدنه یک")
    cs.add_text(session, "عنوان دو")
    assert cs.finish_texts(session) is None

    from agents.carousel.schema import CarouselSlide
    from agents.carousel.deck_renderer import CarouselDeck
    from agents.carousel.planner import CarouselPlanResult
    slides = [CarouselSlide(slide_type="cover", title="کاور",
                            image_path=session["images"][0])]
    slides.append(CarouselSlide(slide_type="image_text", title="تصویر ۱",
                                image_path=session["images"][1],
                                image_layout="auto"))
    deck = CarouselDeck(title="دک تست", template="psychological_dark",
                        slides=slides)
    planner = MagicMock()
    planner.plan.return_value = CarouselPlanResult(
        deck=deck, caption="", hashtags=[], provider_used=None)
    renderer = make_fake_renderer(tmp_path)
    error = cs.build_deck(session, planner=planner, renderer=renderer)
    assert error is None
    assert session["state"] == cs.PREVIEW
    return session


def _fake_resume_renderer(tmp_path):
    renderer = make_fake_renderer(tmp_path)
    renderer.slide_renderer = MagicMock()
    return renderer


def test_M29_session_timeout_is_six_hours():
    cs = import_cs()
    assert cs.SESSION_TIMEOUT_MINUTES == 6 * 60
    session = cs.new_session()
    session["created_at"] = time.time() - 5 * 3600
    assert not cs.session_expired(session)
    session["created_at"] = time.time() - 7 * 3600
    assert cs.session_expired(session)
    cs.cleanup(session)


def test_M29_draft_upserted_on_each_step(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    session = _build_persisted_preview(tmp_path, db, storage, tag="u")
    record = db.get_carousel_draft(12345)
    # mode / images / texts all persisted
    assert record["draft"]["mode"] == "text_overlay"
    assert len(record["draft"]["images_keys"]) == 2
    assert storage.uploads == 2
    assert record["draft"]["texts"][0] == {"title": "عنوان یک", "body": "بدنه یک"}
    # preview built -> deck persisted
    assert record["draft"]["deck"] is not None
    assert len(record["draft"]["deck"]["slides"]) == 2
    # edit applied -> draft follows
    err, path = cs.edit_slide(session, 2, "عنوان ویرایش‌شده")
    assert err is None
    record = db.get_carousel_draft(12345)
    assert record["draft"]["deck"]["slides"][1]["title"] == "عنوان ویرایش‌شده"
    cs.cleanup(session)


def test_M29_resume_latest_draft(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    session = _build_persisted_preview(tmp_path, db, storage, tag="r")
    cs.cleanup(session)  # simulate bot restart: in-memory session gone

    chat_data = {}
    message, error = cs.resume_carousel_draft(
        chat_data, db, storage, 12345, renderer=_fake_resume_renderer(tmp_path))
    assert error is None
    assert "بازیابی شد" in message
    resumed = chat_data["carousel_session"]
    assert resumed["state"] == cs.PREVIEW
    assert len(resumed["images"]) == 2
    assert all(os.path.exists(p) for p in resumed["images"])
    assert resumed["deck"] is not None
    assert len(resumed["slide_paths"]) == 2
    # images came from storage, not the old local paths
    assert storage.downloads == 2
    assert resumed["mode"] == "text_overlay"
    assert resumed["texts"][0] == {"title": "عنوان یک", "body": "بدنه یک"}
    cs.cleanup(resumed)


def test_M29_resume_then_edit_without_reupload(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    session = _build_persisted_preview(tmp_path, db, storage, tag="e")
    cs.cleanup(session)

    chat_data = {}
    _, error = cs.resume_carousel_draft(
        chat_data, db, storage, 12345, renderer=_fake_resume_renderer(tmp_path))
    assert error is None
    resumed = chat_data["carousel_session"]
    uploads_after_resume = storage.uploads

    err, path = cs.edit_slide(resumed, 2, "عنوان بعد از رزوم")
    assert err is None
    assert resumed["deck"].slides[1].title == "عنوان بعد از رزوم"
    # no re-upload of the source images
    assert storage.uploads == uploads_after_resume
    cs.cleanup(resumed)


def test_M29_resume_specific_custom_id(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()

    session = _build_persisted_preview(tmp_path, db, storage, tag="f")
    renderer = make_fake_renderer(tmp_path)
    renderer.upload_deck_to_storage = (
        lambda paths, cid, storage: [f"carousel/{cid}/s{i}.png"
                                     for i in range(len(paths))])
    error, info = cs.finalize(session, storage, FakeItemDB(),
                              custom_id="ELN-CAR-A", renderer=renderer)
    assert error is None
    assert info["custom_id"] == "ELN-CAR-A"
    cs.cleanup(session)

    # A second draft generation overwrites the CURRENT state...
    session2 = _build_persisted_preview(tmp_path, db, storage, tag="g")
    record = db.get_carousel_draft(12345)
    assert record["custom_id"] is None
    # ...but the history keeps the finalized version
    assert [h["custom_id"] for h in record["draft"]["history"]] == ["ELN-CAR-A"]
    cs.cleanup(session2)

    chat_data = {}
    message, error = cs.resume_carousel_draft(
        chat_data, db, storage, 12345, "ELN-CAR-A",
        renderer=_fake_resume_renderer(tmp_path))
    assert error is None
    resumed = chat_data["carousel_session"]
    assert resumed["custom_id"] == "ELN-CAR-A"
    assert resumed["state"] == cs.PREVIEW
    cs.cleanup(resumed)

    # Unknown id -> honest error
    _, error = cs.resume_carousel_draft(
        {}, db, storage, 12345, "ELN-CAR-NOPE",
        renderer=_fake_resume_renderer(tmp_path))
    assert error and "پیدا نشد" in error


def test_M29_resume_expired_draft_rejected(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    session = _build_persisted_preview(tmp_path, db, storage, tag="x")
    cs.cleanup(session)
    # age the draft beyond the 30-day window
    record = db.get_carousel_draft(12345)
    record["updated_at"] = "2026-01-01T00:00:00+00:00"
    _, error = cs.resume_carousel_draft(
        {}, db, storage, 12345, renderer=_fake_resume_renderer(tmp_path))
    assert error and "منقضی" in error


def test_M29_resume_active_session_conflict(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    session = _build_persisted_preview(tmp_path, db, storage, tag="c")
    chat_data = {"carousel_session": session}
    _, error = cs.resume_carousel_draft(
        chat_data, db, storage, 12345, renderer=_fake_resume_renderer(tmp_path))
    assert error and "فعال است" in error
    cs.cleanup(session)


def test_M29_carousel_list_shows_recent(tmp_path):
    cs = import_cs()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    session = _build_persisted_preview(tmp_path, db, storage, tag="l")
    renderer = make_fake_renderer(tmp_path)
    renderer.upload_deck_to_storage = (
        lambda paths, cid, storage: [f"carousel/{cid}/s{i}.png"
                                     for i in range(len(paths))])
    error, _ = cs.finalize(session, storage, FakeItemDB(),
                           custom_id="ELN-CAR-A", renderer=renderer)
    assert error is None
    cs.cleanup(session)

    reply = cs.list_carousels_fa(db, 12345)
    assert "ELN-CAR-A" in reply
    assert "دک تست" in reply
    # no draft for another owner
    empty = cs.list_carousels_fa(FakeDraftDB(), 99999)
    assert "پیدا نشد" in empty


@pytest.mark.asyncio
async def test_M29_cancel_clears_persistent_draft(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    session = cs.new_session()
    db, storage = FakeDraftDB(), FakeMediaStorage()
    cs.attach_persistence(session, db, storage, 12345)
    context.chat_data["carousel_session"] = session
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_cancel(update, context)
    assert context.chat_data["carousel_session"] is None
    assert 12345 in db.deleted
    assert "حذف شد" in update.message.reply_text.call_args[0][0]
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M29_reply_add_readds_image(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True, text="ثبت")
    session = cs.new_session()
    session["state"] = cs.COLLECT_IMAGES
    session["mode"] = "text_overlay"
    context.chat_data["carousel_session"] = session
    # a previously sent image message, now replied to
    file_obj = MagicMock()
    file_obj.download_to_drive = AsyncMock(
        side_effect=lambda p: (open(p, "wb").write(b"REPLIED_IMG"), None)[1])
    photo = MagicMock()
    photo.get_file = AsyncMock(return_value=file_obj)
    replied = MagicMock()
    replied.photo = [photo]
    replied.document = None
    update.message.reply_to_message = replied
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)
    assert len(session["images"]) == 1
    assert os.path.exists(session["images"][0])
    reply = update.message.reply_text.call_args[0][0]
    assert "دوباره ثبت شد" in reply
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M29_reply_add_readds_text(tmp_path):
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True, text="ثبت")
    session = cs.new_session()
    session["state"] = cs.COLLECT_TEXTS
    session["mode"] = "text_overlay"
    context.chat_data["carousel_session"] = session
    replied = MagicMock()
    replied.text = "عنوان قبلی | بدنه قبلی"
    replied.photo = None
    replied.document = None
    replied.caption = None
    update.message.reply_to_message = replied
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)
    assert session["texts"] == [{"title": "عنوان قبلی", "body": "بدنه قبلی"}]
    reply = update.message.reply_text.call_args[0][0]
    assert "دوباره ثبت شد" in reply
    cs.cleanup(session)


def _preview_session(tmp_path, n_slides=3):
    cs = import_cs()
    session = cs.new_session()
    session["state"] = cs.PREVIEW
    session["mode"] = "text_overlay"
    from agents.carousel.schema import CarouselSlide
    from agents.carousel.deck_renderer import CarouselDeck
    slides = [CarouselSlide(slide_type="cover", title="کاور",
                            image_path=f"/img/0.jpg")]
    for i in range(1, n_slides):
        slides.append(CarouselSlide(slide_type="image_text",
                                    title=f"تصویر {i}",
                                    image_path=f"/img/{i}.jpg"))
    session["deck"] = CarouselDeck(title="دک", template="psychological_dark",
                                   slides=slides)
    session["slide_paths"] = [write_image(tmp_path, f"s{i}.png")
                              for i in range(n_slides)]
    renderer = MagicMock()
    renderer.slide_renderer = MagicMock()
    session["_renderer"] = renderer
    session["preview_media_group_id"] = "group-1"
    session["preview_first_message_id"] = 100
    return session


@pytest.mark.asyncio
async def test_M29_reply_replace_pending_then_image(tmp_path):
    bot = import_bot()
    cs = import_cs()
    session = _preview_session(tmp_path)
    context = MagicMock()
    context.chat_data = {"carousel_session": session}
    context.chat_id = 12345

    # «جایگزین» on slide 2's preview message (first_id + 1)
    update, _ = make_mock_update(is_owner=True, text="جایگزین")
    replied = MagicMock()
    replied.message_id = 101
    replied.media_group_id = "group-1"
    update.message.reply_to_message = replied
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)
    assert session["pending_replace_slide"] == 2
    reply = update.message.reply_text.call_args[0][0]
    assert "جایگزین اسلاید 2" in reply

    # the replacement image arrives as a plain photo
    img_update, _ = make_mock_update(is_owner=True, with_photo=True)
    img_update.message.photo[0].get_file.return_value.download_to_drive.side_effect = \
        lambda p: (open(p, "wb").write(b"NEW_IMG"), None)[1]
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(img_update, context)
    assert session["pending_replace_slide"] is None
    assert session["deck"].slides[1].image_path.endswith("replace_02.jpg")
    caption = img_update.message.reply_photo.call_args.kwargs["caption"]
    assert "جایگزین شد" in caption
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M29_reply_replace_direct_with_image(tmp_path):
    bot = import_bot()
    cs = import_cs()
    session = _preview_session(tmp_path)
    context = MagicMock()
    context.chat_data = {"carousel_session": session}
    context.chat_id = 12345

    # image + «جایگزین» caption in one reply to slide 3
    update, _ = make_mock_update(is_owner=True, with_photo=True)
    update.message.text = None
    update.message.caption = "جایگزین"
    update.message.photo[0].get_file.return_value.download_to_drive.side_effect = \
        lambda p: (open(p, "wb").write(b"NEW_IMG_3"), None)[1]
    replied = MagicMock()
    replied.message_id = 102
    replied.media_group_id = "group-1"
    update.message.reply_to_message = replied
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)
    assert session["deck"].slides[2].image_path.endswith("replace_03.jpg")
    caption = update.message.reply_photo.call_args.kwargs["caption"]
    assert "جایگزین شد" in caption
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M29_reply_replace_unknown_slide_clear_error(tmp_path):
    bot = import_bot()
    cs = import_cs()
    session = _preview_session(tmp_path)
    context = MagicMock()
    context.chat_data = {"carousel_session": session}
    context.chat_id = 12345

    # replying to a message that is NOT part of the current preview group
    update, _ = make_mock_update(is_owner=True, text="جایگزین")
    replied = MagicMock()
    replied.message_id = 42
    replied.media_group_id = "other-group"
    update.message.reply_to_message = replied
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)
    reply = update.message.reply_text.call_args[0][0]
    assert "پیدا نکردم" in reply
    assert session["pending_replace_slide"] is None
    cs.cleanup(session)


@pytest.mark.asyncio
async def test_M29_normal_intake_unchanged_without_reply(tmp_path):
    """A plain «ثبت» WITHOUT reply_to_message is normal text intake — no
    session side effects (the shortcut only works on replies)."""
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True, text="ثبت")
    session = cs.new_session()
    session["state"] = cs.COLLECT_TEXTS
    context.chat_data["carousel_session"] = session
    update.message.reply_to_message = None
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.handle_studio_media(update, context)
    # normal COLLECT_TEXTS handling: the text is added as a slide text
    assert session["texts"] == [{"title": "ثبت", "body": ""}]
    cs.cleanup(session)


# === M29A: draft ownership must use the Telegram chat id (bigint-safe) ===

@pytest.mark.asyncio
async def test_M29A_carousel_list_uses_effective_chat_id(tmp_path):
    """A: /carousel_list keys the query by update.effective_chat.id —
    NOT context.chat_id (which is None in production)."""
    bot = import_bot()
    cs = import_cs()
    update, context = make_mock_update(is_owner=True)
    # context.chat_id is the bug source: None (app-level conversation id)
    context.chat_id = None
    # update.effective_chat.id = OWNER ("12345", a numeric string)
    db = FakeDraftDB()
    with patch("agents.db.supabase_client.ElinaDB", return_value=db), \
         patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_list(update, context)
    # The query received the normalized INT chat id, never None/"None"
    assert db.received_chat_ids, "list must query the draft table"
    assert all(isinstance(v, int) for v in db.received_chat_ids)
    assert 12345 in db.received_chat_ids
    assert None not in db.received_chat_ids
    assert "None" not in db.received_chat_ids


@pytest.mark.asyncio
async def test_M29A_carousel_resume_uses_effective_chat_id(tmp_path):
    """B: /carousel_resume keys the query by update.effective_chat.id —
    NOT context.chat_id (None in production)."""
    bot = import_bot()
    update, context = make_mock_update(is_owner=True)
    context.chat_id = None
    db = FakeDraftDB()
    storage = FakeMediaStorage()
    with patch("agents.db.supabase_client.ElinaDB", return_value=db), \
         patch("agents.storage.supabase_storage.ElinaStorage", return_value=storage), \
         patch.object(bot, "OWNER_CHAT_ID", OWNER):
        await bot.cmd_carousel_resume(update, context)
    assert db.received_chat_ids, "resume must query the draft table"
    assert all(isinstance(v, int) for v in db.received_chat_ids)
    assert 12345 in db.received_chat_ids
    assert None not in db.received_chat_ids
    assert "None" not in db.received_chat_ids


def test_M29A_draft_upsert_uses_normalized_int_chat_id(tmp_path):
    """C: draft persistence stores/queries the owner id as a real int,
    even when the chat id is handed over as a numeric string."""
    cs = import_cs()
    db = FakeDraftDB()
    storage = FakeMediaStorage()
    session = cs.new_session()
    cs.attach_persistence(session, db, storage, "12345")  # numeric string
    # attach_persistence normalizes to int immediately
    assert session["_persistence"]["chat_id"] == 12345
    assert isinstance(session["_persistence"]["chat_id"], int)
    img = write_image(tmp_path, "c1.jpg", b"IMGDATA")
    assert cs.add_image(session, img) is None
    # Every draft query used the normalized int owner id
    assert db.received_chat_ids
    assert all(isinstance(v, int) and v == 12345 for v in db.received_chat_ids)
    cs.cleanup(session)


def test_M29A_normalize_rejects_none():
    """D: normalize_owner_chat_id(None) raises CAROUSEL_OWNER_CHAT_ID_INVALID."""
    cs = import_cs()
    with pytest.raises(Exception) as exc_info:
        cs.normalize_owner_chat_id(None)
    assert exc_info.value.code == cs.CAROUSEL_OWNER_CHAT_ID_INVALID
    assert exc_info.value.code == "CAROUSEL_OWNER_CHAT_ID_INVALID"


def test_M29A_normalize_rejects_string_none():
    """E: normalize_owner_chat_id('None'/'none'/''/whitespace) raises."""
    cs = import_cs()
    for bad in ("None", "none", "NONE", "", "   ", "abc", "12a", True, 0, 3.5):
        with pytest.raises(Exception) as exc_info:
            cs.normalize_owner_chat_id(bad)
        assert exc_info.value.code == "CAROUSEL_OWNER_CHAT_ID_INVALID"


def test_M29A_normalize_numeric_string_returns_int():
    """F: normalize_owner_chat_id('6366392934') returns int 6366392934."""
    cs = import_cs()
    result = cs.normalize_owner_chat_id("6366392934")
    assert result == 6366392934
    assert isinstance(result, int)
    # ints pass through unchanged; surrounding whitespace is stripped
    assert cs.normalize_owner_chat_id(6366392934) == 6366392934
    assert cs.normalize_owner_chat_id(" 6366392934 ") == 6366392934


def test_M29A_db_query_never_receives_none_string(monkeypatch):
    """G: the Supabase adapter rejects None/'None' BEFORE any query runs —
    the bigint column can never be queried with None or 'None'."""
    import agents.db.supabase_client as db_mod
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_SECRET_KEY", "secret")
    db = db_mod.ElinaDB()

    class _BoomClient:
        """Fails loudly if any query is attempted for a bad owner id."""
        def table(self, *a, **k):
            raise AssertionError("query must not run for None/'None'")

    db.client = _BoomClient()
    for bad in (None, "None", "none", "", "   "):
        with pytest.raises(Exception) as exc_info:
            db.get_carousel_draft(bad)
        assert exc_info.value.code == "CAROUSEL_OWNER_CHAT_ID_INVALID"
        with pytest.raises(Exception) as exc_info:
            db.upsert_carousel_draft(bad, {})
        assert exc_info.value.code == "CAROUSEL_OWNER_CHAT_ID_INVALID"
        with pytest.raises(Exception) as exc_info:
            db.delete_carousel_draft(bad)
        assert exc_info.value.code == "CAROUSEL_OWNER_CHAT_ID_INVALID"


def test_M29A_owner_permission_uses_env_not_ownership(monkeypatch):
    """H: /whoami and owner permission are UNCHANGED — is_owner still
    compares effective_chat.id to the OWNER_CHAT_ID env var (permission),
    independent of the M29A draft-ownership normalization."""
    bot = import_bot()
    update, _ = make_mock_update(is_owner=True)      # effective_chat.id = "12345"
    stranger, _ = make_mock_update(is_owner=False)   # effective_chat.id = "99999"
    with patch.object(bot, "OWNER_CHAT_ID", OWNER):
        # permission is still env-based: effective_chat.id vs OWNER_CHAT_ID
        assert bot.is_owner(update) is True
        assert bot.is_owner(stranger) is False
    # A non-owner id is never treated as owner, even though it normalizes
    # to a perfectly valid int — ownership normalization did not touch perms
    with patch.object(bot, "OWNER_CHAT_ID", "12345"):
        assert bot.is_owner(stranger) is False
