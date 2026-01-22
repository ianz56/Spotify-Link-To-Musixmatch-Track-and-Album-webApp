from babel.messages.frontend import CommandLineInterface


def main():
    """
    Compile gettext translations in the 'translations' directory using Babel's CLI.
    
    Runs Babel's CommandLineInterface to execute `pybabel compile -d translations`. Prints "Compiling translations..." before execution and prints any exception raised during the run.
    """
    cli = CommandLineInterface()
    print("Compiling translations...")
    try:
        cli.run(["pybabel", "compile", "-d", "translations"])
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()