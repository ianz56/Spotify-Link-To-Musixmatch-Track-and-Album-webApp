from babel.messages.frontend import CommandLineInterface


def main():
    """
    Run Babel message extraction for the current project and write results to messages.pot.
    
    Invokes Babel's command-line extraction using babel.cfg as the configuration and a maximum line width of 2500, extracting message strings from the current directory into the file `messages.pot`.
    """
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