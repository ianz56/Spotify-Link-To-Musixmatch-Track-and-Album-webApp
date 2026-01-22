from babel.messages.frontend import CommandLineInterface


def main():
    """
    Initialize gettext translation directories for Indonesian ('id') and English ('en') using pybabel.
    
    Runs the babel CommandLineInterface to invoke the equivalent of `pybabel init -i messages.pot -d translations -l <lang>` for languages "id" and "en". Prints progress messages and any exception raised during each initialization.
    """
    cli = CommandLineInterface()
    print("Initializing ID...")
    try:
        cli.run(
            ["pybabel", "init", "-i", "messages.pot", "-d", "translations", "-l", "id"]
        )
    except Exception as e:
        print(e)

    print("Initializing EN...")
    try:
        cli.run(
            ["pybabel", "init", "-i", "messages.pot", "-d", "translations", "-l", "en"]
        )
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()