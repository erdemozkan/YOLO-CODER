"""
Pre-flight check: verify the AI backend is reachable before YOLO starts.

On success  → prints a fancy "brain online" banner with the model name.
On failure  → prints a clear error + provider-specific instructions, then exits.
"""

import sys
import urllib.request
import urllib.error
import json
from colorama import Fore, Style
from core.config import ModelConfig


def _fetch_models(cfg: ModelConfig) -> list[str]:
    """
    Hit the provider's health/model-list endpoint.
    Returns a list of loaded model name strings.
    Raises urllib.error.URLError / OSError on connection failure.
    """
    req = urllib.request.Request(cfg.health_url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(req, timeout=4) as resp:
        data = json.loads(resp.read().decode())

    models_list = data.get(cfg.health_models_key, [])
    return [m.get(cfg.health_name_field, "") for m in models_list if m]


def _print_online(cfg: ModelConfig, loaded_models: list[str]) -> None:
    """Print the 'brain online' success banner."""
    W  = Fore.WHITE  + Style.BRIGHT
    G  = Fore.GREEN  + Style.BRIGHT
    C  = Fore.CYAN   + Style.BRIGHT
    M  = Fore.MAGENTA
    DIM = Style.RESET_ALL + Fore.WHITE
    R  = Style.RESET_ALL

    # Which model name to highlight — prefer the configured model if present
    active = cfg.model if cfg.model in loaded_models else (loaded_models[0] if loaded_models else "unknown")

    print(f"{M}┌{'─' * 52}┐")
    print(f"{M}│{W}  🧠  YOLO BRAIN ONLINE{' ' * 31}{M}│")
    print(f"{M}├{'─' * 52}┤")
    print(f"{M}│{DIM}  Provider : {C}{cfg.provider:<39}{M}│{R}")
    print(f"{M}│{DIM}  Endpoint : {W}{cfg.base_url:<39}{M}│{R}")
    print(f"{M}│{DIM}  Model    : {G}{active:<39}{M}│{R}")

    if len(loaded_models) > 1:
        others = ", ".join(m for m in loaded_models if m != active)
        # Truncate if too long for the box
        if len(others) > 38:
            others = others[:35] + "..."
        print(f"{M}│{DIM}  Also     : {DIM}{others:<39}{M}│{R}")

    print(f"{M}└{'─' * 52}┘{R}\n")


def _print_offline(cfg: ModelConfig, error: str) -> None:
    """Print the 'brain offline' error banner + instructions."""
    R  = Fore.RED    + Style.BRIGHT
    Y  = Fore.YELLOW + Style.BRIGHT
    W  = Fore.WHITE
    RS = Style.RESET_ALL

    print(f"{R}┌{'─' * 52}┐")
    print(f"{R}│  🚫  AI MODEL NOT RUNNING{' ' * 27}│")
    print(f"{R}├{'─' * 52}┤")
    print(f"{R}│{W}  Provider : {cfg.provider:<39}{R}│{RS}")
    print(f"{R}│{W}  Expected : {cfg.base_url:<39}{R}│{RS}")
    print(f"{R}│{W}  Error    : {error[:39]:<39}{R}│{RS}")
    print(f"{R}└{'─' * 52}┘{RS}")

    instructions = cfg.run_instructions()
    print(f"\n{Y}How to start {cfg.provider}:{RS}")
    for step in instructions:
        print(f"  {W}→{RS} {step}")

    print(
        f"\n{Y}To use a different provider:{RS}\n"
        f"  {W}yolo --provider lmstudio <command>{RS}\n"
        f"  {W}yolo --provider llamacpp --port 8080 <command>{RS}\n"
        f"  {W}yolo --host 192.168.1.10 --port 11434 <command>{RS}"
    )
    print()


def run_preflight(cfg: ModelConfig) -> None:
    """
    Check that the AI backend is reachable and a model is loaded.
    Prints success/failure banner and exits on failure.
    """
    try:
        loaded_models = _fetch_models(cfg)
    except (urllib.error.URLError, OSError, TimeoutError) as e:
        _print_offline(cfg, str(e).split("]")[-1].strip())
        sys.exit(1)
    except Exception as e:
        _print_offline(cfg, str(e)[:60])
        sys.exit(1)

    if not loaded_models:
        _print_offline(cfg, "Server reachable but no models are loaded")
        sys.exit(1)

    _print_online(cfg, loaded_models)
