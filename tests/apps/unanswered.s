| Unanswered: a window that needs drawing, and an event loop that looks
| only for a click, as Cap'n Magneto's title screen has: GetNextEvent
| gives it the window's update event each time it asks.  Its 30 calls
| one after another take about 30 ticks, not a few: asked again in the
| same tick for the update it was just given, GetNextEvent waits for the
| next.  Then it asks until the mouse goes down.

        .include "traps.inc"

QD              = -4            | InitGraf(@thePort)
EVENT           = -226          | an EventRecord
PHASE           = -228          | 1 asking 30 times, 2 asking for a click
UPDATES         = -232          | the update events among the 30
TOOK            = -236          | the ticks the 30 took
PRESSED         = -240          | the Ticks when the click came
GLOBALS         = 240

TICKS           = 0x16A
TIMES           = 30
mouseDown       = 1
updateEvt       = 6

start:
        pea     QD(a5)
        _InitGraf
        _InitFonts
        _InitWindows
        _InitCursor
        clr.l   -(sp)
        clr.l   -(sp)                   | its storage, in the heap
        pea     bounds(pc)
        pea     title(pc)
        move.w  #0x0100, -(sp)          | visible
        move.w  #4, -(sp)               | noGrowDocProc
        moveq   #-1, d0
        move.l  d0, -(sp)               | in front
        clr.w   -(sp)                   | no close box
        clr.l   -(sp)
        _NewWindow
        addq.l  #4, sp

        move.w  #1, PHASE(a5)
        move.l  TICKS, d6
        moveq   #0, d5
        moveq   #TIMES-1, d7
1:      bsr.s   look
        cmpi.w  #updateEvt, EVENT(a5)
        bne.s   2f
        addq.l  #1, d5
2:      dbra    d7, 1b
        move.l  TICKS, d0
        sub.l   d6, d0
        move.l  d0, TOOK(a5)
        move.l  d5, UPDATES(a5)

        move.w  #2, PHASE(a5)
3:      _SystemTask
        bsr.s   look
        cmpi.w  #mouseDown, EVENT(a5)
        bne.s   3b
        move.l  TICKS, PRESSED(a5)
        _ExitToShell

look:
        clr.w   -(sp)
        move.w  #-1, -(sp)              | everyEvent
        pea     EVENT(a5)
        _GetNextEvent
        addq.l  #2, sp
        rts

bounds: .short  60, 40, 200, 300
title:  .byte   10
        .ascii  "Unanswered"
        .even
