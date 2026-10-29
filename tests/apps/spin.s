| Spin: waiting by asking over and over, as early games do, with nothing
| else in the loop: for TickCount to come to a second on, then for Button
| to say the mouse is down.  It'd keep the host's processor busy all the
| while; the asking goes on as fast, but after a little of it the program
| waits for the next tick or for input.

        .include "traps.inc"

PHASE           = -2            | 1 asking TickCount, 2 asking Button
CALLS           = -6            | its calls to TickCount
TOOK            = -10           | the ticks the second took
PRESSED         = -14           | the Ticks when Button said the mouse was down
GLOBALS         = 14

TICKS           = 0x16A

start:
        move.w  #1, PHASE(a5)
        clr.l   -(sp)
        _TickCount
        move.l  (sp), d6                | when it started
        move.l  (sp)+, d4
        add.l   #60, d4                 | a second on
        moveq   #0, d5
1:      addq.l  #1, d5
        clr.l   -(sp)
        _TickCount
        cmp.l   (sp)+, d4
        bhi.s   1b
        move.l  TICKS, d0
        sub.l   d6, d0
        move.l  d0, TOOK(a5)
        move.l  d5, CALLS(a5)

        move.w  #2, PHASE(a5)
2:      clr.w   -(sp)
        _Button
        tst.b   (sp)+
        beq.s   2b
        move.l  TICKS, PRESSED(a5)
        _ExitToShell
