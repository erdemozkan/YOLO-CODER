class Yolo < Formula
  include Language::Python::Virtualenv

  desc "AI agent that fixes your broken CLI commands automatically using a local LLM"
  homepage "https://github.com/erdemozkan/YOLO-APR"
  url "https://github.com/erdemozkan/YOLO-APR/archive/refs/tags/v0.0.2.tar.gz"
  # sha256 will be filled in after the release tarball is published
  # sha256 "FILL_IN_AFTER_RELEASE"
  license "MIT"

  depends_on "python@3.12"

  resource "openai" do
    url "https://files.pythonhosted.org/packages/source/o/openai/openai-1.30.1.tar.gz"
    sha256 "" # fill in on release
  end

  resource "colorama" do
    url "https://files.pythonhosted.org/packages/source/c/colorama/colorama-0.4.6.tar.gz"
    sha256 "08695f5cb7ed6e0531a20572697297d53cf2f73cfcded5dc2fffb8e8e4ce0ef0"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/source/r/rich/rich-13.7.1.tar.gz"
    sha256 "" # fill in on release
  end

  resource "python-dotenv" do
    url "https://files.pythonhosted.org/packages/source/p/python-dotenv/python_dotenv-1.0.1.tar.gz"
    sha256 "" # fill in on release
  end

  def install
    virtualenv_install_with_resources
  end

  def caveats
    <<~EOS
      YOLO requires Ollama to be running with a supported model.

      Install Ollama:
        brew install ollama

      Pull the recommended model:
        ollama pull qwen2.5-coder:7b

      Then run:
        yolo python3 myapp.py
    EOS
  end

  test do
    assert_match "YOLO", shell_output("#{bin}/yolo --help 2>&1", 1)
  end
end
