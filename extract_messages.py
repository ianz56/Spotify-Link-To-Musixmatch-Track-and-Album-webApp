from babel.messages.frontend import CommandLineInterface

import update_translations


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
            "messages.pot",
            "--width=2500",
            ".",
        ]
    )
    update_translations.main()


if __name__ == "__main__":
    main()
