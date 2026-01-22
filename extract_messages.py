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
            "messages.pot",
            "--width=2500",
            ".",
        ]
    )


if __name__ == "__main__":
    main()
