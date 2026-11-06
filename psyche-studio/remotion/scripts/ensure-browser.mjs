/**
 * Resolve a Chromium binary and a static ffmpeg for THIS sandbox, then print
 * shell exports for Remotion.
 *
 * Why this exists: the sandbox has no preinstalled Chrome, no ffmpeg and no
 * root access for apt. Remotion's usual download host (remotion.media) is not
 * reachable either, so `npx remotion browser ensure` cannot work here.
 *
 * Strategy, in order:
 *   1. Remotion's own browser cache (used when the download host works).
 *   2. @sparticuz/chromium (npm, works in this sandbox) + its bundled NSS libs.
 *   3. The system Chrome, if the user has one.
 *
 * ...and for ffmpeg:
 *   1. `ffmpeg` on PATH.
 *   2. imageio-ffmpeg's static binary via Python (pip, works in this sandbox).
 *
 * Output is shell assignments, meant to be used as:
 *   eval "$(node scripts/ensure-browser.mjs)"
 *   npx remotion render ...      # picks up REMOTION_BROWSER_EXECUTABLE + PATH
 *
 * This is sandbox-only tooling. CI never needs it: GitHub's ubuntu-latest
 * runners can download Remotion's Chrome Headless Shell the normal way.
 */
import { execFileSync } from "node:child_process";
import { createRequire } from "node:module";
import fs from "node:fs";
import os from "node:os";
import path from "node:path";

const require = createRequire(import.meta.url);
const log = (m) => console.error(`[ensure-browser] ${m}`);

function sh(value) {
  return `'${String(value).replace(/'/g, `'\\''`)}'`;
}

function executable(p) {
  try {
    fs.accessSync(p, fs.constants.X_OK);
    return true;
  } catch {
    return false;
  }
}

function remotionCacheChrome() {
  const candidates = [
    path.join(os.homedir(), ".cache", "remotion", "chrome-headless-shell"),
    path.join(process.cwd(), "node_modules", ".remotion", "chrome-headless-shell"),
  ];
  for (const dir of candidates) {
    if (!fs.existsSync(dir)) continue;
    const stack = [dir];
    while (stack.length) {
      const cur = stack.pop();
      for (const entry of fs.readdirSync(cur, { withFileTypes: true })) {
        const full = path.join(cur, entry.name);
        if (entry.isDirectory()) stack.push(full);
        else if (entry.name === "chrome-headless-shell" && executable(full)) return full;
      }
    }
  }
  return null;
}

function sparticuzChrome() {
  let sparticuz;
  try {
    sparticuz = require("@sparticuz/chromium").default ??
      require("@sparticuz/chromium");
  } catch {
    return null;
  }
  // The package does not export ./package.json, so locate it via the entry file.
  const pkgRoot = path.dirname(path.dirname(require.resolve("@sparticuz/chromium")));
  const libDir = path.join(pkgRoot, ".al2023-libs");
  const libFile = path.join(libDir, "lib", "libnss3.so");

  if (!fs.existsSync(libFile)) {
    // The brotli archive only carries the NSS/NSRP libs the bundled Chromium
    // needs on a minimal Debian image.
    const archive = fs.readFileSync(path.join(pkgRoot, "bin", "al2023.tar.br"));
    const tarPath = path.join(os.tmpdir(), "al2023-libs.tar");
    fs.writeFileSync(tarPath, require("node:zlib").brotliDecompressSync(archive));
    fs.mkdirSync(libDir, { recursive: true });
    execFileSync("tar", ["xf", tarPath, "-C", libDir], { stdio: "ignore" });
    log(`extracted NSS libs to ${libDir}`);
  }
  return { libDir };
}

function ffmpegPath() {
  try {
    const which = execFileSync("sh", ["-c", "command -v ffmpeg"], { encoding: "utf8" }).trim();
    if (which) return which;
  } catch {
    /* not on PATH */
  }
  try {
    const py = execFileSync(
      "python3",
      ["-c", "import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())"],
      { encoding: "utf8", env: { ...process.env, PYTHONPATH: process.env.PYTHONPATH ?? "" } },
    ).trim();
    if (py && executable(py)) return py;
  } catch {
    /* python package missing */
  }
  return null;
}

const exports = [];

let chrome = remotionCacheChrome();
let extraLibDirs = [];
if (!chrome) {
  try {
    const sparticuz = require("@sparticuz/chromium").default;
    chrome = await sparticuz.executablePath();
    const libs = sparticuzChrome();
    if (libs) extraLibDirs.push(path.join(libs.libDir, "lib"));
    // SwiftShader (software WebGL) ships next to the binary.
    const vulkanDir = path.dirname(chrome);
    if (fs.existsSync(path.join(vulkanDir, "libvk_swiftshader.so"))) {
      extraLibDirs.push(vulkanDir);
    }
    log(`using @sparticuz/chromium at ${chrome}`);
  } catch (err) {
    log(`@sparticuz/chromium unavailable: ${err.message}`);
  }
}
if (!chrome) {
  for (const guess of ["/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser"]) {
    if (executable(guess)) {
      chrome = guess;
      break;
    }
  }
}

if (!chrome) {
  log("no Chromium found; run `npx remotion browser ensure` on a machine with internet access");
  process.exit(1);
}

exports.push(`export REMOTION_BROWSER_EXECUTABLE=${sh(chrome)}`);

if (extraLibDirs.length) {
  const existing = process.env.LD_LIBRARY_PATH ? `:${process.env.LD_LIBRARY_PATH}` : "";
  exports.push(
    `export LD_LIBRARY_PATH=${sh(extraLibDirs.join(":") + existing)}`,
  );
}

// Software WebGL. Headless Chromium on a GPU-less runner has no other option.
exports.push(
  `export REMOTION_CHROMIUM_FLAGS=${sh(
    [
      "--no-sandbox",
      "--disable-dev-shm-usage",
      "--disable-gpu-sandbox",
      "--use-gl=angle",
      "--use-angle=swiftshader",
      "--enable-unsafe-swiftshader",
    ].join(" "),
  )}`,
);

const ffmpeg = ffmpegPath();
if (ffmpeg) {
  // Remotion calls `ffmpeg`/`ffprobe` by name, so a shim directory is easiest.
  const shimDir = path.join(os.tmpdir(), "remotion-ffmpeg-shim");
  fs.mkdirSync(shimDir, { recursive: true });
  const ffmpegLink = path.join(shimDir, "ffmpeg");
  fs.rmSync(ffmpegLink, { force: true });
  fs.symlinkSync(ffmpeg, ffmpegLink);
  const ffprobeGuess = ffmpeg.replace(/ffmpeg$/, "ffprobe");
  if (ffprobeGuess !== ffmpeg && executable(ffprobeGuess)) {
    const probeLink = path.join(shimDir, "ffprobe");
    fs.rmSync(probeLink, { force: true });
    fs.symlinkSync(ffprobeGuess, probeLink);
  }
  exports.push(`export PATH=${sh(shimDir)}:"$PATH"`);
  log(`ffmpeg shim -> ${ffmpeg}`);
} else {
  log("no ffmpeg found; PNG-sequence rendering will still work, encoding will not");
}

process.stdout.write(exports.join("\n") + "\n");
