class Yoco < Formula
  include Language::Python::Virtualenv

  desc "AI agent that fixes your broken CLI commands automatically using a local LLM"
  homepage "https://github.com/erdemozkan/YOLO-CODER"

  url "https://github.com/erdemozkan/YOLO-CODER/archive/refs/tags/v0.02.tar.gz"
  sha256 "9ed4814f7744dfc2d38514e65eac2a08d8cafc54a4a0e217fd48cf2db0a5249c"
  license "MIT"

  depends_on "python@3.12"

  resource "openai" do
    url "https://files.pythonhosted.org/packages/e6/9e/108827f9a558335f07d7ad1f22b733a0e48990337cfbf923c49cd78f8f78/openai-1.30.1.tar.gz"
    sha256 "4f85190e577cba0b066e1950b8eb9b11d25bc7ebcc43a86b326ce1bfa564ec74"
  end

  resource "colorama" do
    url "https://files.pythonhosted.org/packages/d8/53/6f443c9a4a8358a93a6792e2acffb9d9d5cb0a5cfd8802644b7b1c9a02e4/colorama-0.4.6.tar.gz"
    sha256 "08695f5cb7ed6e0531a20572697297273c47b8cae5a63ffc6d6ed5c201be6e44"
  end

  resource "rich" do
    url "https://files.pythonhosted.org/packages/b3/01/c954e134dc440ab5f96952fe52b4fdc64225530320a910473c1fe270d9aa/rich-13.7.1.tar.gz"
    sha256 "9be308cb1fe2f1f57d67ce99e95af38a1e2bc71ad9813b0e247cf7ffbcc3a432"
  end

  resource "python-dotenv" do
    url "https://files.pythonhosted.org/packages/bc/57/e84d88dfe0aec03b7a2d4327012c1627ab5f03652216c63d49846d7a6c58/python-dotenv-1.0.1.tar.gz"
    sha256 "e324ee90a023d808f1959c46bcbc04446a10ced277783dc6ee09987c37ec10ca"
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
    system bin/"yoco", "--help"
  end
end
