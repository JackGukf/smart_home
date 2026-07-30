from src.python.controller import startup_message


def test_startup_message_names_orange_pi_controller() -> None:
    assert startup_message() == "Smart Home Orange Pi 6 Plus Python controller starting..."
