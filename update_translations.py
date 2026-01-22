from babel.messages.frontend import CommandLineInterface


def main():
    """
    Run the Babel CLI to update translation catalogs.
    
    Invokes a CommandLineInterface to perform a `pybabel update` using "messages.pot" as the input template and "translations" as the output directory, and prints a progress message to stdout. If an exception occurs during the update, the exception is printed.
    """
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
                "--width=2500",
            ]
        )
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()