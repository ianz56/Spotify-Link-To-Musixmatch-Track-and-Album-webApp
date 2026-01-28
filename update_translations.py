import sys

from babel.messages.frontend import CommandLineInterface


def main():
    cli = CommandLineInterface()
    print("Updating translations...")
    try:
        cli.run(
            [
                "pybabel",
                "update",
                "-i",
                "messages.pot",
                "-d",
                "translations",
                "-l",
                "en",
                "--width=2500",
            ]
        )
    except Exception as e:
        print(e)
        sys.exit(1)


if __name__ == "__main__":
    main()
