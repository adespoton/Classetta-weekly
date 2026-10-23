| Panel: a control panel, its code 'cdev' -4064.  At initDev it makes a
| handle, its storage, with a word in it saying whether it was sent
| cdevUnset.  macDev is answered with the word at runs_here, which the
| tests change.  A hit on item 1, its button, is cdevGenErr, which closes
| it; one on item 2, its checkbox, toggles that.  A key 'x' it takes for
| itself, making the event a null one.  Anything else, it returns its
| storage as it was given it.

        .include "traps.inc"

initDev         = 0
hitDev          = 1
keyEvtDev       = 7
macDev          = 8
cdevUnset       = 3
cdevGenErr      = -1
UNSET           = 0             | in its storage

| cdev(message, item, numItems, CPrivateValue: INTEGER; VAR theEvent:
|      EventRecord; cdevStorageValue: LONGINT; CPDialog: DialogPtr): LONGINT
dialog          = 8
storage         = 12
event           = 16
item            = 24
message         = 26
result          = 28
ARGS            = 20
kind            = -2            | GetDialogItem's
control         = -6
box             = -14

        .text
cdev:
        bra.s   start
runs_here:
        .short  1
start:
        link    a6, #-14
        move.l  storage(a6), d0
        move.w  message(a6), d1
        cmpi.w  #initDev, d1
        beq.s   init
        cmpi.w  #macDev, d1
        beq.s   mac
        cmpi.w  #hitDev, d1
        beq.s   hit
        cmpi.w  #keyEvtDev, d1
        beq.s   key
done:
        move.l  d0, result(a6)
        unlk    a6
        movea.l (sp)+, a0
        adda.w  #ARGS, sp
        jmp     (a0)

init:
        moveq   #2, d0
        .short  0xA322                  | _NewHandle ,CLEAR
        movea.l (a0), a1
        cmpi.l  #cdevUnset, storage(a6)
        seq     UNSET(a1)
        move.l  a0, d0
        bra.s   done

mac:
        moveq   #0, d0
        move.w  runs_here(pc), d0
        bra.s   done

key:
        movea.l event(a6), a0
        cmpi.b  #'x', 5(a0)             | the character, in the message's low byte
        bne.s   done
        clr.w   (a0)                    | nullEvent
        bra.s   done

hit:
        cmpi.w  #1, item(a6)
        bne.s   1f
        moveq   #cdevGenErr, d0
        bra.s   done
1:      cmpi.w  #2, item(a6)
        bne.s   done
        move.l  dialog(a6), -(sp)
        move.w  #2, -(sp)
        pea     kind(a6)
        pea     control(a6)
        pea     box(a6)
        _GetDialogItem
        clr.w   -(sp)
        move.l  control(a6), -(sp)
        _GetControlValue
        move.w  (sp)+, d0
        eori.w  #1, d0
        move.l  control(a6), -(sp)
        move.w  d0, -(sp)
        _SetControlValue
        move.l  storage(a6), d0
        bra.s   done
