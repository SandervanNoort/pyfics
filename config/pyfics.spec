[rgb]
    white = int_list(default=list(237, 193, 106))
    black = int_list(default=list(139, 69, 19))
    move = int_list(default=list(255, 0, 0))
    premove = int_list(default=list(0, 0, 255))
[window]
    height = integer(default=579)
    width = integer(default=1024)
    pane = integer(default=708)
    moves_tab = integer(default=200)

[fics]
    user = string(default="")
    password = string(default="")
    guest_init = string_list(default=list("-ch 4", "-ch 53", "set seek 0", "set formula lightning | blitz"))
    server = string(default="freechess.org")
    port = integer(default=23)

[menu]
    Seek = string_list(default=list("Seek 1 0 f", "Seek 1 1 f", "Seek 3 0 f", "sought", "Unsought"))
    Examine = string_list(default=list("Examine", "Unexamine"))
    Accept = string_list(default=list("Accept", "Decline"))
