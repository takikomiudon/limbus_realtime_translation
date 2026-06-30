"""main

Backward-compatible command entrypoint for the realtime translation client.
The implementation is split into the client package for testable modules.
"""

from client.app import main

if __name__ == "__main__":
    main()
