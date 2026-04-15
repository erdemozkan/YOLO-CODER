# ⚠️  WORK IN PROGRESS — NOT READY FOR USE
#
# This Homebrew formula is incomplete and will NOT install correctly.
# SHA256 checksums can only be generated after a versioned GitHub release
# tarball exists. See instructions at the bottom of this file.
#
# Current status: placeholder — do not submit to homebrew-core or share publicly.

class Yoco < Formula
  include Language::Python::Virtualenv

  desc "AI agent that fixes your broken CLI commands automatically using a local LLM"
  homepage "https://github.com/erdemozkan/YOLO-CODER"

  # TODO: update URL and fill sha256 after publishing a GitHub release tag
  url "https://github.com/erdemozkan/YOLO-CODER/archive/refs/tags/v0.0.2.tar.gz"
  sha256 "FILL_IN_AFTER_RELEASE"
  license "MIT"

  depends_on "python@3.12"

  # TODO: fill sha256 for each resource (see instructions below)
  resource "openai" do
    url "https://files.pythonhosted.org/packages/source/o/openai/openai-1.30.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "colorama" do
    url "https://files.pythonhosted.org/packages/source/c/colorama/colorama-0.4.6.tar.gz"
    sha256 "08695f5cb7ed6e0531a20572697297d53cf2f73cfcded5dc2fffb8e8e4ce0ef0"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.1.tar.gz"
    sha256 "FILL_IN"
  end

  resource "python-dotenv" do
    url "https://files.pythonhosted.org/packages/source/p/python-dotenv/python_dotenv-1.0.1.tar.gz"
    sha256 "FILL_IN"
  end

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      YOCO requires Ollama to be running with a supported model.

      Install Ollama:
        brew install ollama

      Pull the recommended model:
        ollama run hf.co/erdemozkan/YOLO-1.5B-Qwen-Coder

      Then run:
        yoco python3 myapp.py
    EOS
  end

  test do
    assert_match "YOLO", shell_output("#{bin}/yoco --help 2>&1", 1)
  end
end

# ─────────────────────────────────────────────────────────────────────────────
# HOW TO COMPLETE THIS FORMULA
# ─────────────────────────────────────────────────────────────────────────────
#
# Step 1 — Publish a GitHub release
#   Go to https://github.com/erdemozkan/YOLO-CODER/releases/new
#   Tag: v0.0.2 (or the current version)
#   GitHub auto-generates the tarball at the URL already in this file.
#
# Step 2 — Get the SHA256 for the release tarball
#   curl -sL https://github.com/erdemozkan/YOLO-CODER/archive/refs/tags/v0.0.2.tar.gz | shasum -a 256
#   Paste the result into: sha256 "FILL_IN_AFTER_RELEASE"
#
# Step 3 — Get SHA256s for each PyPI dependency
#   curl -sL https://files.pythonhosted.org/packages/source/o/openai/openai-1.30.1.tar.gz | shasum -a 256
#   curl -sL https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.1.tar.gz | shasum -a 256
#   curl -sL https://files.pythonhosted.org/packages/source/p/python-dotenv/python_dotenv-1.0.1.tar.gz | shasum -a 256
#   Paste each result into the matching sha256 "FILL_IN" field above.
#
# Step 4 — Test the formula locally
#   brew install --build-from-source Formula/yoco.rb
#   yoco --help
#
# Step 5 — Done. Formula is ready to submit or share.
# ─────────────────────────────────────────────────────────────────────────────
