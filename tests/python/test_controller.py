from src.python.controller import startup_message


def test_startup_message_names_raspberry_pi_controller() -> None:
    assert startup_message() == "Smart Home Raspberry Pi 4 Python controller starting..."
