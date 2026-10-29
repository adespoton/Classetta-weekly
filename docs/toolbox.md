# What works

Part of [Running a Mac application](running-apps.md).

macrt answers more than 700 Toolbox and Operating System routines. Here
they are, a manager at a time:

- [Memory Manager](#memory-manager)
- [Segment Loader](#segment-loader)
- [Resource Manager](#resource-manager)
- [QuickDraw](#quickdraw)
- [Font Manager](#font-manager)
- [Colour windows](#colour-windows)
- [Palette Manager](#palette-manager)
- [Color Picker Package (`Pack12`)](#color-picker-package-pack12)
- [Window Manager](#window-manager)
- [Menu Manager](#menu-manager)
- [Help Manager](#help-manager)
- [Event Manager](#event-manager)
- [Control Manager](#control-manager)
- [Dialog Manager](#dialog-manager)
- [List Manager](#list-manager)
- [TextEdit](#textedit)
- [Scrap Manager](#scrap-manager)
- [File Manager](#file-manager)
- [Device Manager](#device-manager)
- [Desk Manager](#desk-manager)
- [Alias Manager](#alias-manager)
- [Standard File](#standard-file)
- [Icons](#icons)
- [Process Manager and MultiFinder](#process-manager-and-multifinder)
- [Apple Event Manager](#apple-event-manager)
- [Edition Manager](#edition-manager)
- [Component Manager](#component-manager)
- [Communications Toolbox utilities](#communications-toolbox-utilities)
- [PPC Toolbox](#ppc-toolbox)
- [SANE](#sane)
- [International Utilities](#international-utilities)
- [Script Manager](#script-manager)
- [Other managers](#other-managers)
- [The hardware](#the-hardware)
- [Printing Manager](#printing-manager)
- [Sound](#sound)
- [Not yet](#not-yet)

## Memory Manager

Handles, pointers, heap zones, purging, the system
heap, and MultiFinder's temporary memory, from a zone of its own above
the applications' partitions. A block that grows, with
`SetPtrSize` or `SetHandleSize`, grows where it is when the relocatable
blocks after it can be moved or purged out of the way, and blocks are a
multiple of 2 bytes long on a 68000 and of 4 on later processors, as
the ROM makes them. `MoveHHi` moves a block up to the first block above
it that can't move, and `ResrvMem` makes room low in the zone, moving
handles up out of the way, so that a block a program keeps locked
doesn't split the room it needs for the large ones it allocates next,
as Stratego's offscreen pixel maps need. `MaxMem` purges every
purgeable block that isn't locked before it compacts the zone, and
`PurgeMem` purges them, lowest first, only until there's room, moving
nothing; a resource or segment purged is read in again the next time
it's asked for.

## Segment Loader

`LoadSeg`, `UnloadSeg` (given an address in the
segment or one of its jump-table entries, as Pascal's `@` gives; an
entry may be called through an address with flags in its top byte,
which a 68000 ignores),
`GetAppParms`, `ExitToShell` and `_Launch`.

## Resource Manager

The resource chain, from the application down to
the System file; `OpenResFile` for files next to the application;
adding, changing and writing resources; reading and writing part of
one in its file (`ReadPartialResource`, `WritePartialResource`,
`SetResourceSize`); and an application's own patch
on `_ResourceStub`, through which it reads resources in, as some
installers, and applications compressed by AutoDoubler, do to decompress
theirs. A resource asked for by ID that isn't found leaves `ResError`
`noErr`, as Microsoft File and Director's projectors count on: Foo
Castle asks for a `VWCI` for each member of its cast, which few have.
One asked for by name is `resNotFound` only when the last file looked
in (the System file, or the current one for `Get1NamedResource`) has
its type. `RGetResource` looks where `GetResource` does: macrt's ROM
has no resources of its own. Compressed resources are expanded as
they're read in, by macrt or by the `dcmp` they name (see [A real
System file](running-apps.md#a-real-system-file)), and `SizeResource` gives their
size expanded. A resource read in goes in the system heap if its
`resSysHeap` attribute says so, and otherwise in the current zone when
that's the system heap or one the program made with `InitZone`, as an
`INIT` sets it to keep what it reads; else in the heap of the
application whose file it's from.

## QuickDraw

In black and white:
- ports, regions, patterns, polygons, every shape, text, measured
  by `MeasureText` too, and `CopyBits`;
- a port's own `textProc` and `txMeasProc`, which draw and measure
  its text in place of `StdText` and `StdTxMeas`, and its own
  `bitsProc`, which `CopyBits` into the port's `portBits` calls in
  place of `StdBits`, as HyperCard 2.2's AddColor has it put its
  colour over a card;
- a port's own `rectProc`, `rRectProc`, `ovalProc`, `arcProc`,
  `polyProc` and `rgnProc`, which draw its shapes in place of
  `StdRect` and the rest, TextEdit's erasing included (its
  `lineProc` isn't called);
- pictures, played and recorded;
- cursors: the program's cursor (`SetCursor`) is your pointer's shape
  over its windows, or over the screen with `--host screen`, and
  `HideCursor`, `ShowCursor` and `ObscureCursor` hide and show it.
  The standard arrow is your own pointer, and the menu bar keeps it.
  The host's pointer can't invert what's under it, so a cursor's
  inverting pixels are black;
- `CopyMask`, `SeedFill` and `CalcMask`, and in colour `SeedCFill`
  and `CalcCMask`, which ask a program's own `matchProc` which pixels
  are edges when it gives one (Director's projectors draw their
  sprites' matte ink through `CalcCMask`);
- `Random`, from `randSeed`; a program can seed it from `RndSeed`,
  in low memory, which is different each time macrt starts;
- colour calls, mapped to black and white on a Mac Plus;
- on a Mac II (`--model ii`), a colour screen: its graphics device,
  which `DeviceLoop` passes to a program's drawing procedure with its
  depth, its pixel map and colour table, which a program can change with
  `SetEntries` and the Color Manager's other calls (`ProtectEntry`
  keeps an entry from `SetEntries`, and `ReserveEntry` from being
  matched to a colour). What QuickDraw draws is in the nearest of its
  colours to the eight classic ones;
- the screen's video driver (`.Display_Video_Apple_TFB`, reference
  number -49), whose `Control` and `Status` calls set and get its mode
  (1, 2, 4 or 8 bits a pixel, up to the depth macrt started the screen
  at with `--depth`), its colours (`SetEntries`, `GetEntries`,
  `SetGray`), and fill it with grey (`GrayPage`). `InitGDevice`,
  `HasDepth` and `SetDepth` change the depth through it, and the ports
  on the screen go with it. An old `GrafPort`, or a `BitMap` whose
  pixels are the screen's, draws on a colour screen at its depth, in
  its colours, as Color QuickDraw's do. There's one page and no gamma
  table;
- the screen's card, in slot 9, and the Slot Manager, which reads its
  declaration ROM. The ROM is macrt's own, laid out as Designing Cards
  and Drivers for the Macintosh Family describes a card's: its format
  block, with a CRC that checks, the board's sResource and the screen's
  (`catDisplay`, `typVideo`, `drSwApple`, and a `DrHW` of 0, macrt's own),
  whose driver is the video driver above, and a mode list for each mode
  the driver has, with its video parameters. Programs find it with
  `SNextTypeSRsrc` and the other searches, and read it with `SReadByte`,
  `SFindStruct`, `SGetBlock` and the rest, as the CyberFlix demos (Jump
  Raven, Lunicus, Western) do to see which depths the screen has.
  `SReadInfo`, `SReadFHeader`, `SFindDevBase` (the screen's pixels),
  the card's parameter RAM and the Slot Resource Table's calls are
  there too. The calls only the Operating System makes, and those that
  load and run a card's own code (`SGetDriver`, `SExec`), aren't. A Mac
  Plus has no slots: `GetTrapAddress` says the Slot Manager isn't
  there, and it finds no cards;
- the ADB Manager's device table (`CountADBs`, `GetIndADB`,
  `GetADBInfo`, `SetADBInfo`), with the keyboard at address 2 and the
  mouse at 3. macrt's keyboard and mouse come from the host, so their
  service routines, which a program can read and replace, are never
  called; `ADBOp` and `ADBReInit` aren't there. On a Mac Plus,
  `GetTrapAddress` says the ADB Manager isn't there;
- colour ports (`OpenCPort`, `CGrafPort`s), which draw in RGB colours
  (`RGBForeColor` and the rest) and with pixel patterns (`NewPixPat`,
  `GetPixPat` from a `ppat` resource, `MakeRGBPat`, `PenPixPat`,
  `FillCRect` and the other `FillC` calls), and `GetCPixel` and
  `SetCPixel`. `ColorBit` sets the port's colour plane for a printer,
  and changes nothing on the screen. An RGB pattern draws as the
  nearest colour the screen has, not dithered. A picture plays its pixel patterns and RGB
  colours in a colour port, and `OpenPicture` in one records a version
  2 picture, which keeps them; `CopyBits` into it is recorded in black
  and white;
- a program's own search procedures (`AddSearch`, `DelSearch`), which
  `Color2Index` asks for a colour's index before the screen's inverse
  table, the last added first, and which `CopyBits` asks for the
  indexes of a black-and-white source's black and white in a colour
  port: NetTrek draws its ships in each side's colours through one;
- colour cursors (`GetCCursor` from a `crsr` resource, `SetCCursor`,
  `DisposeCCursor`), shown in their colours on a screen of more than
  2 bits a pixel, and as their black-and-white cursor on one of 1 or 2;
- offscreen pixel maps (`NewPixMap`, `CopyPixMap`, `SetPortPix`): a
  colour port draws on one of 2 to 8 bits in pixel values, its
  foreground and background colours' indexes, and `CopyBits` copies
  pixel values as they are between pixel maps of one colour table, and
  matches colours between others and to the screen. In a source mode
  but Copy (`srcOr`, `notSrcBic` and the rest), in a black foreground
  and a white background, it combines the source's values with the
  destination's bit by bit, as Inside Macintosh V has the modes apply
  to a colour source's 1s and 0s: FloorTiles masks its coloured tiles
  offscreen that way;
- 32-Bit QuickDraw's offscreen graphics worlds (`NewGWorld`,
  `SetGWorld`, `GetGWorld`, `UpdateGWorld`, `DisposeGWorld`,
  `GetGWorldPixMap`, `LockPixels` and the rest of `QDExtensions`, and
  `NewScreenBuffer`): a colour port onto pixels of its own, with a
  graphics device of its own, so that what's drawn in it is in the
  nearest of its own colour table's colours. Made with depth 0, a world
  is like the screen its rectangle (a global one) is on, and is that
  rectangle's size, with its top left at 0,0. `SetGWorld` with no device
  makes the main screen's device current for a port on the screen, as
  for a window a program goes back to from a world. `Gestalt` says a Mac II has
  32-Bit QuickDraw 1.2, and `QD32Trap` ($AB03) is there for a program
  that looks for it with `GetTrapAddress` instead, as Pico does. A
  `QDExtensions` call is the selector in D0's low word, so an old
  program's `moveq` of a selector alone reaches it too. How it differs
  from a Mac's: a world's pixels
  are never purged (`GetPixelsState` says what a program asked for),
  and `UpdateGWorld` scales an image with `stretchPix` but doesn't
  dither it (`ditherPix`);

## Font Manager

Font names and numbers (`GetFontName`, `GetFNum`),
`RealFont`, `SetFractEnable` and `SetFScaleDisable`, and `FMSwapFont`,
which picks the bitmap font or your computer's font for a request,
fills in its output record and leaves the global width table for it in
the system heap, where `WidthTabHandle`, `WidthPtr` and `WidthListHand`
find it (Inside Macintosh IV, the Font Manager): each character's
width as QuickDraw draws it, Microsoft Word 4 adding up its lines from
them. `FontMetrics` gives `GetFontInfo`'s measures in fixed point, and
the table's handle. There are no outline fonts (`IsOutline`);

## Colour windows

`NewCWindow` and `GetNewCWindow` make a window
whose port is a colour port, its colours in its auxiliary record
(`SetWinColor`, `GetAuxWin`, a `wctb` resource), or the default
record's, from the application's `wctb` 0. Its content is erased in its
content colour, as it is when the window is shown. On a colour Mac any
window's frame is drawn in its table's colours, as near as the screen
has them: its outline, the line under its title bar, its boxes and its
shadow in the frame colour, its title in the text colour, its stripes
in the highlight colour and the title bar behind them in the title bar
colour, which is how macrt reads the parts' names; a dialog box's
white band is in the content colour. A rounded window's frame is black
and white.

## Palette Manager

A colour window's palette (`NewPalette`,
`GetNewPalette` from a `pltt` resource, and the one `GetNewCWindow`
gives a window from the `pltt` of its ID) gives the screen its colours
when the window comes to the front: each tolerant colour an index of
its own, changed if it isn't close enough, and each animated colour an
index reserved for it, which nothing else is drawn in, so that
`AnimateEntry` and `AnimatePalette` change what's drawn in it at once.
`PmForeColor` and `PmBackColor` draw in a palette's colours, and an
application can have a default palette for windows without one.
A PixMap in the screen's colour table that's copied to a window
(`CopyBits`) is put on the screen as its pixels' values, an animated
index's too, so that a picture copied while its colours are all black
appears as they're animated: Lemmings fades its screens in that way.
Nigel's World sets its colours this way. How it differs from a Mac's:
- there's one screen to give colours to, and no update events for a
  change of colours, which aren't needed: what's on the screen is shown
  in its new colours;
- an animated colour takes the highest index no other entry needs
  (an explicit one, `pmAnimated + pmExplicit`, the index of its entry),
  rather than the one least used by the windows on the screen;
- the screen's colour table may have one colour more than once, but
  what macrt shows of a window is in colours, not indexes, so an entry
  whose colour another has (an index reserved for animation, or any but
  the first of others alike) is shown a step from it (in red, green or
  blue, out of 255), and `Index2Color` gives that colour. A port whose
  foreground or background index has the colour it asks for keeps that
  index, so a program can set the screen's entries all black with
  `RestoreEntries`, draw, and fade in what it drew, as Zoop does;
- an entry inhibited from a depth (`pmInhibitC8` and the rest) is
  left off only a colour screen of that depth, macrt's screen being a
  colour one.

## Color Picker Package (`Pack12`)

Colours converted between RGB,
CMY, HSL and HSV (`RGB2HSV` and the rest, `Fix2SmallFract` and
`SmallFract2Fix`), and `GetColor`, which asks with your computer's own
colour dialog, the program's prompt as its title. The dialog keeps 8
bits of each component, so a colour changed in it comes back to that
precision.

## Window Manager

The standard window kinds, with dragging, growing,
zooming and update regions; between `BeginUpdate` and `EndUpdate` only
what's in the update region is drawn. A window with the application's
own `WDEF`, a resource or code it put in `windowDefProc` itself, is that
code's to shape and draw: the window takes the shape of the structure
region it works out, shows the frame it draws, and its `wHit` answer
says where a click is. An application's `WDEF` that passes messages to
the System's `WDEF` 0 or 1, as Excel's do, gets macrt's frames. A
`WDEF` written before Color QuickDraw finds a colour window's bounds
where a black-and-white window's `portBits.bounds` are, as it works out
the window's regions. A colour `WDEF` that draws in the colour Window
Manager port (`GetCWMgrPort`), as BMAPEdit's does, draws its frame there
as well as in `WMgrPort`. The desk is drawn in `DeskPattern`, or with
Color QuickDraw in the pixel pattern `SetDeskCPat` gives it, when
`PaintOne` is called with no window, as Desktop Patterns does. What of
the menu bar a program has put in `GrayRgn` is desk then too, as
HyperCard's `hide menuBar` has it, until the bar is drawn again.
An application starts with `WWExist` and `QDExist` set, saying the
Window Manager and QuickDraw aren't set up yet; `InitGraf` and
`InitWindows` clear them. Burtonia's THINK C console sets up the
Toolbox only if they say it isn't.

## Menu Manager

`MENU` and `MBAR` resources, key equivalents, marks,
styles and `AppendResMenu`. Hierarchical menus: a submenu inserted
with `InsertMenu(menu, hierMenu)` goes in the menu list's hierarchical
section, not the bar (Inside Macintosh V, the Menu Manager), and an
item with `hMenuCmd` ($1B) as its key opens the submenu its mark names,
to its right. `MenuSelect` and `MenuKey` return the submenu's ID with
its items.
A menu with the application's own `MDEF`, a resource or code it put
in `menuProc` itself, is that code's to size, draw and track: the
menu pulled down shows what it draws, in the Window Manager port, and
its `mChooseMsg` answer says which item the mouse is over.
`PopUpMenuSelect` puts a pop-up menu, its own `MDEF`'s or a standard
one, with the chosen item at the point given, below the menu bar, and
`CalcMenuSize` asks the `MDEF` for the menu's size. An `MDEF` that sets
the port's font and passes messages to the System's `MDEF` 0, as
Theldrow's does, gets its menus drawn in that font.
With Color QuickDraw (`--model ii`), the menu colour table in
`MenuCInfo` colours the bar, its titles and the items the host draws.
`InitMenus` makes it, with the entries of the `mctb` 0, and
`ClearMenuBar` and `GetNewMBar` empty it;
`GetMenu`, and so `GetNewMBar`, adds the entries of the `mctb` with the
menu's ID, as Glider 4's menus have, and `GetMCEntry`, `SetMCEntries`,
`DelMCEntries`, `GetMCInfo`, `SetMCInfo` and `DispMCInfo` work on the
table (Inside Macintosh V, the Menu Manager). A title's entry gives its
colour, the bar's behind it, its items' and its menu's background, in
that order, as Digital Messiah's grey-on-black menus have them. A
highlighted item swaps its text and background colours.
A title of five bytes, $01 and an icon suite's handle, shows as the
suite's small icon, as Apple's Technical Q&A TB 06 has a program make
one: BBEdit 3.1 has two such menus.
As on System 7, the Application menu, and the Help menu once an
application has one, come after the application's own menus in its menu
list, whatever it does to them: HyperCard 2's `doMenu "Hide Others"`
looks for its item there.

## Help Manager

System 7's Help menu. `HMGetHelpMenuHandle` gives an
application its own copy of it, with About Balloon Help and Show
Balloons, for it to append its items to (Inside Macintosh: More
Macintosh Toolbox, 3-83). Once it has, the menu's balloon is at the
right of the bar, and `MenuSelect` and `MenuKey` return
`kHMHelpMenuID` (-16490) with one of its items. Balloons aren't shown:
`HMGetBalloons` is false, as with Show Balloons off, and the two
standard items are dimmed. `HMShowBalloon` and `HMShowMenuBalloon` say
help is off (`hmHelpDisabled`); the balloons' font and size, and the
`hdlg` and `hmnu` resource IDs an application sets, it gets back.

## Event Manager

`GetNextEvent`, `WaitNextEvent`, `EventAvail`,
`Button`, `GetKeys`, `PostEvent` and `FlushEvents`. `GetNextEvent` with
nothing to give returns at once, unless it's asked again in the same
tick: then it waits for the next, so that a program's event loop
leaves the host the processor. A program that waits by calling
`TickCount`, `Button`, `EventAvail`, `GetMouse`, `StillDown`, `GetKeys`,
`WaitMouseUp`, `OSEventAvail`, `GetOSEvent` or `SystemTask` over and
over, with nothing else between, as Lemmings and Airborne! do, leaves it
the processor too: after 2 ms of that in a row, it waits for the next
tick or for input, which is what it's asking about. One that does a
little work between such calls still has 2 ms of the host each tick,
many ticks of a Mac's work. With `--speed` it isn't done: there the
time a program takes is the point. An update event a program passes
over comes each time it asks, until it draws the window with
`BeginUpdate` and `EndUpdate`, as on a Mac; Cap'n Magneto's title
screen looks only for a click and never does. Asked again in the same
tick for an update it was given and hasn't begun, `GetNextEvent` and
`WaitNextEvent` wait for the next tick, or for input, first.
`WaitNextEvent` gets its event through
a program's patch on `GetNextEvent`, as on a Mac: HyperCard 2 hands
its main loop a click it noticed while a script ran that way.
`StillDown` is false once the mouse-up is in the queue, and
`WaitMouseUp`, like the Toolbox's tracking calls (`TrackControl`,
`TEClick`, `DragGrayRgn` and a window's drag and grow), takes the
mouse-up that ended the press out of the queue (Inside Macintosh I,
Toolbox Event Manager). `KeyTranslate` uses the US layout whatever `KCHR` it's given, and
`GetScriptManagerVariable(smKCHRCache)` points to that layout as a
`KCHR`.

## Control Manager

Buttons, check boxes, radio buttons and scroll bars,
whose titles may have several lines separated by returns, each line of a
button's centered and those of a check box or radio button
left-justified, the lines a font's leading apart and centered together
in the control (Inside Macintosh IV, The Control Manager),
plus the application's own 68k `CDEF`s, including code it puts in a
control record's `contrlDefProc` itself, and a `CDEF` 0 or 1 of its
own, which is found before the System's and takes its place (Flash 2
draws its buttons with one). Pop-up menus (`CDEF` 63,
procIDs 1008 to 1023, as System 7 has them)
are macrt's too, with or without a System file: a title, then a box
with the chosen item and a down arrow. `TrackControl` pops the menu
up over the box with that item checked, and the item chosen becomes
the value. The variations work: `popupFixedWidth`, `popupUseAddResMenu`
and `popupUseWFont`, as do the title's style and justification
(Inside Macintosh VI, the Control Manager). Controls have auxiliary
records with colour tables (`SetCtlColor`, `GetAuxCtl`, from
`AuxCtlHead`) for an application's own `CDEF` to draw with; macrt's
standard controls are drawn in black and white. With Color QuickDraw,
`InitWindows` makes the default records for windows and controls, at
the end of their lists (Inside Macintosh V).

## Dialog Manager

Modal and modeless dialogs, alerts, `ParamText`,
filter procedures and the item calls, with edit fields edited through
TextEdit. On a colour machine a `GetNewDialog` dialog is a colour
window when there's a `dctb` of its ID, and an alert when there's an
`actb`, in that table's colours, as `NewColorDialog`'s are. Without one
it's an old grafPort, as Inside Macintosh V says, which programs that
draw straight into a dialog's `portBits` count on (Pinball Arcade).
`NewDialog`'s are black-and-white ones.

## List Manager

Lists drawn by `LDEF` 0 or the application's own
`LDEF`, with clicks, Shift and Command to extend the selection,
dragging, autoscrolling, scroll bars and double clicks. Cells are kept
where the ROM keeps them, so code that reads a list's record and its
data directly sees what it expects.

## TextEdit

Editing, selection, line breaking, scrolling, styled text
and `TETextBox`; and the routine at `TEDoText`, for programs that find,
highlight, draw and place the caret through it themselves. A record's
`highHook` and `caretHook` are called as TextEdit's own, `_InvertRect`,
is: the rectangle's address on the stack, for the hook to pop.

## Scrap Manager

The desk scrap. Text in it is shared with your
computer's clipboard, both ways. `UnloadScrap` writes it to the
Clipboard File in the System Folder, as a Mac does.

## File Manager

Files, folders and volumes, the HFS catalog calls,
working directories, the `FSSpec` calls and `FindFolder`. See
[Documents and saving](running-apps.md#documents-and-saving).

## Device Manager

An application's own drivers, the `DRVR` resources
in its file. `Open` finds one by name and puts it in the unit table, and
`Read`, `Write`, `Control`, `Status`, `KillIO` and `Close` call its
routines, synchronously, asynchronously or immediately; the driver
finishes each request through `IODone`, which calls the request's
completion routine. `Open` finds the System file's drivers too, from
`--system` or the disk's System (see [A real System
file](running-apps.md#a-real-system-file)), except where macrt has its own: the Sound
Driver, `.Print` and `.Sony` (see [Games from 1984](running-apps.md#games-from-1984)),
and the serial ports' `.AIn`, `.AOut`, `.BIn` and `.BOut`, which have
nothing plugged in, so what's written to them goes nowhere and nothing
comes in to read: an asynchronous read waits, its `ioResult` 1, until
`KillIO` or `Close` takes it out with `abortErr`. The ports' use bytes,
`PortAUse` and `PortBUse`, say no driver has either. AppleTalk's drivers aren't opened, as macrt hasn't
its hardware. The unit table and the first drivers' device control
entries are made low in the System heap, under 32K, as a Mac makes them
at startup: Speller Bee's speech driver keeps its registers a word each.
A program can make a device control entry of its own, for a driver
in its memory, with `DriverInstall` (`_DrvrInstall`), and take it out
again with `DriverRemove`, as THINK C's console does for its console
window: Burtonia's.

## Desk Manager

Desk accessories, the `DRVR`s an application lists
in its Apple menu with `AddResMenu`, from the System file (`--system`)
or its own file. `OpenDeskAcc` opens one for the application that
picks it, as a driver. Its window then takes clicks through
`SystemClick`, keys and updates through `SystemEvent`, which
`GetNextEvent` and `WaitNextEvent` call, and the Edit menu through
`SystemEdit`; `SystemTask` gives it time, and a pick from its own menu
goes to it. The Event Manager calls `SystemEvent` and `SystemTask`
through the trap table, so a patch of either sees the calls: After
Dark's `INIT` gets its time that way. With `SEvtEnb` cleared, the
Event Manager doesn't call `SystemEvent`, but a program's own call to
it still goes through: THINK C's console clears it and calls
`SystemEvent` itself, for the keys typed in its window. It closes from its close box, with `CloseDeskAcc`, or when
the application quits. macrt's own System file has no desk
accessories. `AddResMenu` lists them in alphabetical order, as a Mac
Plus does (Inside Macintosh IV-55); a 128K or 512K Mac listed them
in the System file's order, so a game that opens a desk accessory by
its place in the menu may open another one, as Fokker Triplane's
Help does.

## Alias Manager

Alias records in System 7's format, found again
after their file or folder has been moved or renamed, and brought up to
date; `MatchAlias` and `GetAliasInfo`; `ResolveAliasFile`, which follows
the Finder's alias files; and Apple event coercions between an alias
and an `FSSpec`. There are no file servers, so an alias whose disk
isn't there doesn't resolve.

## Standard File

The Open and Save dialogs, filtered by file type and
by the application's own filter procedure. A custom dialog's own items
(its buttons, check boxes, radio buttons, pop-up menus, text and edit
text) are shown under the standard ones, and what it draws itself (user
items, pictures and icons) is shown as it draws it; its `dlgHook` is
called as each is clicked or typed in. MacWrite's choice of formats in
its Save dialog is one, and Microsoft File's name for a new datafile
another. In System 7's `CustomGetFile`, the reply record says what's
selected while the dialog is up, so a hook can let the user pick a
folder: Open with a folder selected returns it. The hook can say where
the dialog starts (`sfHookChangeSelection`), sends `sfHookGoToDesktop`
for the Desktop button, and hears `sfHookNullEvent` when a folder is
shown and each time the selection changes, not between them.
Spoydworks Solitaire finds its Games & Decks folder this way. The modal
filter and activation procedures aren't called.

## Icons

`ICON`, `SICN`, `cicn` and icon families, through the mask; a
`cicn` in its colours when the screen has more than 2 bits a pixel.
`ForEachIconDo` calls a program's icon action function for each type
of icon its selector names, and keeps what the function leaves in the
suite.

## Process Manager and MultiFinder

The process calls, temporary memory
and `SetFrontProcess`.

## Apple Event Manager

Descriptors, lists, records, and Apple events
with their parameters and attributes; the handler tables, object
accessors and object callbacks, kept though nothing resolves object
specifiers; and coercions between numbers, text and four-character
codes, plus the application's own coercion handlers. An application gets the Open
Application event at launch (see [What happens at
launch](running-apps.md#what-happens-at-launch)), can look through what's waiting with
`GetSpecificHighLevelEvent`, and can send events to itself, which is
how recordable applications carry out their own commands.

## Edition Manager

Publishers and subscribers, registered across all
the applications running, and editions written and read through the
application's edition opener, the standard one or its own, with the
standard formats (`TEXT`, `PICT`, `snd `) or any others. When a
publisher's edition changes, its automatic subscribers get a Section
Read event; a publisher whose container has gone gets an empty one and
a Section Write event; `GoToPublisherSection` sends a Section Scroll.
These are Apple events, sent only to applications whose `SIZE` says they
take high-level events. An edition container's data fork is in macrt's
own format, since Inside Macintosh doesn't document Apple's, so macrt
finds no formats in one a real Mac wrote. The Publish and Subscribe
dialogs are Standard File's, the publisher's with a preview of the
edition; the options dialog is macrt's own. The `itemOffset` an expanded
dialog's hook is given counts the items before the expansion: Standard
File's own (12 for a publisher, 9 for a subscriber), or the options
dialog's OK and Cancel (2). None of the dialogs uses `where` or a filter
procedure. `GoToPublisherSection` opens an unregistered publisher's
document only if its application is already running, since macrt
doesn't launch applications itself. `Gestalt`'s `edtn` says the
Edition Manager is there.

## Component Manager

Components registered from a `thng` resource
or by the program, found by their description, opened, called and
closed, with their own storage and A5 world, captured and delegated to.
The Sound control panel's sub-panels are components, in its own file.

## Communications Toolbox utilities

`AppendDITL`, `CountDITL` and
`ShortenDITL`, which add items to a dialog and take them away again, as
the Sound control panel does for each sub-panel. The rest of the
Communications Toolbox isn't there.

## PPC Toolbox

`PPCInit`, and ports opened and closed, as System 7's
applications do at startup, though nothing can connect to them. The
Process Manager names each application's own port. `Gestalt`'s `ppc `
says the toolbox is there and initialised, with no network, and `os  `
that `LaunchApplication` takes an `FSSpec` and can launch an
application without quitting.

## SANE

`FP68K`'s arithmetic, comparisons, conversions and
environment calls, correctly rounded in every rounding direction and
precision, with the Apple Numerics Manual's exceptions, NaN codes and
halts; `Elems68K`'s logarithms, exponentials, powers, financial
functions, trigonometry and random numbers; and `PStr2Dec`, `CStr2Dec`
and `Dec2Str`.

## International Utilities

Dates and times written out as the `INTL`
resources say, `IUMetric`, `IUGetIntl`, `IUSetIntl`, and string
comparison and equality.

## Script Manager

The Roman script only. Character types, upper and
lower case and accents (`Transliterate`, `UppercaseText` and the like),
words (`FindWord`), line breaks (`StyledLineBreak`), `TruncString`,
justified text (`MeasureJust`, `DrawJust`, `Pixel2Char`), and the
Script Manager's variables.

## Other managers

Gestalt, `SysEnvirons`, the Notification Manager
(a request's message is shown at once, and its response procedure
called at the next `GetNextEvent` or `WaitNextEvent` once the alert
has been dismissed),
the date and time, `SysBeep`, VBL tasks (`VInstall` and `VRemove`),
run once a tick while their application runs or waits, and the Time
Manager (`InsTime`, `InsXTime`, `PrimeTime` and `RmvTime`). Below the
interrupted program's stack, a VBL task, a Time Manager task or a sound
channel's callback finds what the interrupt stacked before calling it:
the processor's exception frame and the registers its handler keeps,
A0-A3 and D0-D3 (Inside Macintosh II-200). Factory's sound callback
writes a word above its return address. Gestalt's hardware
attributes (`hdwr`) are the model's: a Mac Plus has a VIA, an SCC and
SCSI, and a Mac II a second VIA and the Apple Sound Chip as well, which
Digital Messiah looks for and writes its music to. On a Mac II the Slot
Manager's VBL tasks (`SlotVInstall`, `SlotVRemove`) run as `VInstall`'s
do, and the Start Manager's `GetVideoDefault` names the screen's card;
a Mac Plus has no slots, and `GetTrapAddress` says these calls aren't
there, so a program that looks for them first, as NetTrek does, leaves
them alone. `HWPriv`'s
cache calls, with no caches to flush. The Package
Manager's `InitPack`, `InitAllPacks`, `DILoad` and `DIUnload` have
nothing to do, every package being always there.

## The hardware

For programs from the Mac's first years: the screen
buffer at `ScrnBase`, the VIA, and the Event Manager's low-memory
record of the mouse and keyboard (see [Games from
1984](running-apps.md#games-from-1984)).

## Printing Manager

The calls of System 6 and 7's `PrGlue`, and the
printer resource file and `.Print` driver that earlier applications
call through, printing to a PDF (see [Printing](running-apps.md#printing)). `PrGeneral`
answers that it can't do what's asked of it, as a printer without those
features does.

## Sound

The Sound Driver's square-wave, four-tone and free-form
sounds, and samples a program puts in the Mac Plus sound buffer, played
through your computer's sound output (see [Sound](running-apps.md#sound)). The Sound
Manager's original calls, `SndPlay` and the channels and their commands,
play through the same buffer, and so do the samples a program writes
to a Mac II's Apple Sound Chip; `SndSoundManagerVersion` says it's
version 2.0, System 7's, or 3.0 on a Mac II when the disk's System is
7.5 or later, and has its double buffering
(`SndPlayDoubleBuffer`), `SndManagerStatus`, `SndChannelStatus`, the
system beep's state and the sound preferences. Play from disk
(`SndStartFilePlay`, `SndPauseFilePlay`, `SndStopFilePlay`) plays AIFF
and AIFF-C files and the sampled sounds of `'snd '` resources, with
their audio selections, and calls the program's completion routine
when the sound ends. The Sound Input Manager finds no device to record
from, as on a Mac Plus or a Mac II, which have none. Speech isn't there
yet.

## Not yet

- Apple events and PPC sessions between applications;
- anything plugged into the serial ports, and AppleTalk;
- in custom Open and Save dialogs, the application's event filter and
  System 7's activation procedures.

An application that calls these gets on as far as it can without them (see
[When it stops](running-apps.md#when-it-stops)).
