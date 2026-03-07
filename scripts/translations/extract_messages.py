import os
from babel.messages.frontend import CommandLineInterface


def main():
    cli = CommandLineInterface()
    # Extract
    print("Extracting messages...")
    cli.run(
        [
            "pybabel",
            "extract",
            "-F",
            "babel.cfg",
            "-o",
            "translations/messages.pot",
            "--width=2500",
            ".",
        ]
    )
    os.system("python scripts/translations/update_translations.py")


if __name__ == "__main__":
    main()
