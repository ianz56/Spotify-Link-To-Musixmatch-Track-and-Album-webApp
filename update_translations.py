from babel.messages.frontend import CommandLineInterface

def main():
    cli = CommandLineInterface()
    print("Updating translations...")
    try:
        cli.run(['pybabel', 'update', '-i', 'messages.pot', '-d', 'translations'])
    except Exception as e:
        print(e)
    
if __name__ == "__main__":
    main()
