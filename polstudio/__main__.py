from polstudio.app import main

# Guard: worker processes (spawn) re-import this module and must not start the GUI
if __name__ == "__main__":
    main()
