| Shy: the driver Driver opens that won't be opened, DRVR 21 ".Shy".  Its
| open routine gives openErr where Inside Macintosh says one gives its
| result, in ioResult, and leaves D0 as it was.

ioResult        = 16

        .text
header:
        .short  0               | no reads, writes, control or status calls
        .short  0, 0, 0         | no delay, event mask or menu
        .short  on_open-header, 0, 0, 0, on_close-header
        .byte   4
        .ascii  ".Shy"
        .even

on_open:
        move.w  #-23, ioResult(a0)      | openErr
        rts

on_close:
        moveq   #0, d0
        rts
