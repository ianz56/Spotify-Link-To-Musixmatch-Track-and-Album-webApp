from babel.messages.frontend import CommandLineInterface


def main():
    cli = CommandLineInterface()
    print("Compiling translations...")
    try:
        cli.run(["pybabel", "compile", "-d", "translations"])
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
