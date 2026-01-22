import os
import sys

from babel.messages.frontend import CommandLineInterface


def main():
    """
    Create a new language translation skeleton using the first command-line argument as the language code.
    
    This function reads sys.argv[1] for the target language code; if no argument is provided it prints usage instructions and returns. It ensures a messages.pot file exists (invoking extract_messages.py when missing), runs Babel's init command to create translations for the given language under translations/<lang_code>/LC_MESSAGES/, and prints next-step guidance for editing and compiling translations. If Babel initialization fails, the function prints the error details.
    """
    if len(sys.argv) < 2:
        print("Usage: python add_language.py <language_code>")
        print("Example: python add_language.py ja")
        return

    lang_code = sys.argv[1]

    # Check if messages.pot exists, if not extract first
    if not os.path.exists("messages.pot"):
        print("messages.pot not found. Extracting messages first...")
        os.system("python extract_messages.py")

    cli = CommandLineInterface()
    print(f"Initializing {lang_code}...")
    try:
        cli.run(
            [
                "pybabel",
                "init",
                "-i",
                "messages.pot",
                "-d",
                "translations",
                "-l",
                lang_code,
            ]
        )
        print(f"\nSuccess! Now edit translations/{lang_code}/LC_MESSAGES/messages.po")
        print("Don't forget to:")
        print("1. Edit the .po file and add translations.")
        print("2. Run 'python compile_translations.py'")
        print(f"3. Add '{lang_code}' to the allowed languages list in app.py")
        print("4. Add a link to the new language in templates/index.html (and others)")
    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()