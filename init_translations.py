from babel.messages.frontend import CommandLineInterface


def main():
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
