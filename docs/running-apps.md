# Running a Mac application

macrt runs classic Mac applications, the programs written for 68000-family
Macs and System 1 to 7, as windows on your desktop next to your own
programs. It reads the application's resources and loads its 68k code
into an emulated processor. Python answers the Toolbox and Operating
System calls that code makes, and PyQt6 draws the result.

This page covers what to install, how to get an application to macrt in a
form it can read, how to run it, and what to do when it stops.

- [Quick start](#quick-start)
- [What you need](#what-you-need)
- [Which applications run](#which-applications-run)
- [Getting the application to macrt](#getting-the-application-to-macrt)
- [Running it](#running-it)
- [What happens at launch](#what-happens-at-launch)
- [What works](#what-works)
- [When it stops](#when-it-stops)
- [Writing a test application](#writing-a-test-application)


## Quick start

```sh
python -m pip install -e .              # PyQt6, unicorn, rsrcfork, machfs
python -m macrt tests/apps/Hello.bin
```

Hello is one of the small test applications in `tests/apps`, written in 68k
assembly. It opens a window and puts up a menu bar; File ▸ Quit ends it, as
does ⌘Q (Ctrl+Q on a PC keyboard). If Hello runs, everything macrt needs is
installed.

Then run your own application:

```sh
python -m macrt MacPaint.bin
python -m macrt "System 6.0.8.dsk" --app TeachText
```

`pip install` also puts a `macrt` command on your path, so `macrt
MacPaint.bin` does the same thing. With no file, macrt runs its two
built-in demo programs instead.


## What you need

- **Python 3.11 or later.**
- **PyQt6** (6.5 or later) for the windows and menus.
- **unicorn** (2.1 or later), the 68k processor emulator.
- **rsrcfork** and **machfs**, which read resource forks and HFS disks'
  B*-trees. (The rest of an HFS disk, and MFS disks, macrt reads itself.)

`pip install -e .` installs all four. unicorn has wheels for Linux, macOS
and Windows.

- **To unpack Mac archives** (StuffIt, Compact Pro and so on), get The
  Unarchiver's command-line tool, `unar`: `apt install unar` or `brew
  install unar`.
- **To run without a display** (a server or CI), set
  `QT_QPA_PLATFORM=offscreen`.


## Which applications run

| What you have | What macrt does |
| --- | --- |
| A 68k application: type `APPL` with `CODE` resources, as for a Mac Plus, SE, II, Classic, LC or a 68k PowerBook | runs it |
| A fat application, with both 68k and PowerPC code | runs the 68k code |
| A PowerPC-only application: a `cfrg` resource and no `CODE` | shows its menus, windows and dialogs from its resources, without running it |
| A self-expanding application, compressed by AutoDoubler | runs it: the application's own decompressor expands its code and resources as they load |
| An application built with MPW's far code model, its `CODE` segments starting with `$FFFF` | runs it when the runtime linked into it loads those segments itself, as Flash 2's does with `ReadPartialResource`; one whose jump table starts with far entries is refused at launch |
| A desk accessory, in the System file or the application's own file | opens it from the application's Apple menu, or wherever the application lists it; it can't be run by itself |
| A control panel: a `cdev` file with code of its own | runs it in a window of its own, as System 7's Finder did (see [Control panels](#control-panels)); a control panel that's an application, as System 7.5's Desktop Patterns is, runs as one |
| Extensions (`INIT` files) | runs a control panel's own `INIT` resources as the panel opens, as a Mac runs them as it starts up (see [Control panels](#control-panels)); an extension that's a file of its own isn't run |

How far an application gets depends on the Toolbox calls it makes (see
[What works](#what-works)). Programs that keep to the Toolbox do best:
word processors, utilities, and games that draw through QuickDraw.
Programs that need Color QuickDraw are less likely to work. Games from
the Mac's first years, which draw straight into the screen and keep time
by its hardware, run with `--host screen --size 512x342`; see [Games from
1984](#games-from-1984).

### Tried so far

These come from the System 6.0.8 disk image, a disk of System 6
utilities, games from the Info-Mac archive, and 400K floppies from the
Mac's first years: System 1.1, MacPaint, MacWrite, Microsoft Word 1.0,
Microsoft Multiplan, Chart and BASIC, MacDraft, Flight Simulator, a disk
of Mac 128K games and more games, and a third set from 1984 to 1987:
SuperPaint, MacWrite 4.5, VideoWorks, Wizardry, Infocom's Hitchhiker's
Guide, Duane Blehm's games and others; and a fourth, mostly games from
1985 to 1990: Déjà Vu, The Oregon Trail, SimCity, Infocom's
Masterpieces, Tom Snyder's simulations and more; and a fifth, from 1987
to 1992: Prince of Persia, Glypha, Ishido, Battle Chess, a disk of
MacGames and a compilation of Mac Plus games; and a sixth, from the
moof-a-day collection's MOOF images: Microsoft Excel 1.0, FullPaint,
Q-Sheet, Dollars and $ense, PFS:FILE, the Deluxe Music Construction
Set, Macintosh Pascal and PageMaker; and a seventh, more games from the
same collection: Falcon, Winter Games, The Ancient Art of War, Hacker,
Hacker II, Shufflepuck Cafe, Ferrari Grand Prix, Déjà Vu II, Dragonworld, The Duel: Test Drive II,
Temple of Apshai Trilogy, Where in Europe Is Carmen Sandiego?,
Sub Battle Simulator,
GATO, The Pawn, Tass Times in Tonetown, Wizardry II, Patton vs. Rommel
and others; and an eighth from it: Angelsoft's interactive fiction
(Goldfinger, The Mist, Rambo), Infocom's A Mind Forever Voyaging, Trinity
and Border Zone, First Byte's Fraction Action, MathTalk and KidTalk,
Physics, MacWars, Where in Time Is Carmen Sandiego?, Harrier Strike
Mission, HardBall, Earl Weaver Baseball, Wizardry VI, Moebius and others;
and more from the Internet Archive's Macintosh Software Library: The
Colony, Pirates!, Railroad Tycoon, Skyfox, Hidden Agenda, Pararena, Race
Car Simulator, HyperCard 1.2.2 and The Manhole, Bolo, Maelstrom, Jetpack,
Crystal Crazy, Duane Blehm's games, Shanghai II, MacRacquetball,
Monopoly, The Hobbit, HyperQuest, NetTrek, Theldrow, Foo Castle, Pico,
MacJack, Dali Clock, Penguin Software's Xyphus and PENSATE, Jeff
Wheeler's EveryMan and Sands of Time, HyperCard 2.4 and Uncle Buddy,
Balance of the Planet, Oh No! More Lemmings, Particle Man, and games
by Lamprey Systems, Ray Dunakin, Mark Pilgrim, S.T. Han, Tony Small and
Dwight Rodgers; Storm Impact's, Foxchange's and Mobuli's games, Bob and
Weave, Zoop, Diamonds, BBEdit 3.1, Glider PRO, HyperCard stacks from
Prisim, FloorTiles, Catch the Buzz, Wordtris and War of Flowers;
Capitalist Pig, the Ert games, The Glider Collection, Xmas Lemmings,
Digital Messiah, a trial of Super Maze Wars, HyperCard 2.2 stacks
coloured with AddColor (Lenny and Rita, StarGuardian, Mr. Fixitup),
Pinball Arcade, Mac Attack, MacGlobe, Heaven & Earth, The Journey,
Maniac, System's Twilight, Magic Castle, StoryMaker and five adventures
from its disk, two Morse code trainers, Rocky Shore Discovery, Rodney's Funscreen, Treasure
MathStorm, Museum Madness, Widget Workshop, The Venice Project, the
games on a disk of them, such as Bulldozer, Ultimine and Hex, with its
browser, HyperCard stacks such as Beyond Cyberpunk, MacJesus, Stranger
Things and the Hitchhiker's Guide's Expanded Book, MacPlay's Monopoly,
The Secret of Monkey Island, Netscape Navigator 2.02 with the web pages
on its disk, a MacPaint demo, Adventures of Sean 2, Apple's tour of the
Macintosh SE, Evocation, The Religion of Islam, HyperCard stacks such as
Clue, the Twin Peaks Bedside Companion and a list of bulletin boards
from 1987, a CD of fifty game demos, the 500 Mac Games CD, Mac Format's
cover floppies, Gary's HyperCard stacks, Thoru Yamamoto's, and others (see
[Where to find software](#where-to-find-software)).

| Application | What happens |
| --- | --- |
| TeachText | Runs: type and edit in its window. |
| Microsoft Excel | Runs: the worksheet, its menus and typing in cells, and quits, asking first whether to save a changed worksheet. |
| Creepy Castle | Plays, with its music and sound effects. Click through the introduction, then double-click a level to start it; the keypad's numbers move and fight. |
| Glider+ 3.1.2 | Plays, with its sounds. Start with Game > Begin Game. |
| Classic Daleks 1.2 | Plays, with its tunes. Start with File > New Game; the keypad's numbers move. |
| Fly Swatter | Plays. Start with File > New Game. |
| Vector 2.5 | Draws its 3D surface. It has no menus. |
| Font/DA Mover 4.1 | With a real System file (`--system`), lists its fonts and desk accessories, shows a sample of the font picked, and removes what you pick. With macrt's own System, which has neither, both lists are empty. |
| DA Piggyback | Shows its introduction. |
| PowerPCheck | File > Scan… asks for an application and reports its 68K and PowerPC code in a window, which File > Save As… saves. |
| LabelWriter II App | Asks for a label list at launch, then shows the label editor, the list and its fields. |
| PrintMonitor | Says it works only when MultiFinder is on, as it does on a Mac without MultiFinder. |
| Disk Copy 4.2 | Shows its introduction and the space it has to copy with. |
| Finder Info 1.1.1 | Asks for a file and shows its Finder information: type and creator, dates and flags. |
| ForkZapper | Asks for a file at launch and erases its data fork, or its resource fork if the Fork pop-up menu under its Open dialog says Resource. |
| StuffIt Expander installer | Shows its introduction and its install dialog, and installs StuffIt Expander where you say, with its Read Us First! folder and an alias of it on the desktop. |
| Operation Tsunami | Plays, with its sounds, with `--model ii`. It's compressed by AutoDoubler, whose notice comes up first: click OK. Then click Play; W, A, S and D move, O shoots, P kicks and the space bar jumps. On the default Plus it draws straight into the screen's memory as if it were a 512×342 Mac's, so its picture lands in the wrong place unless it's run with `--host screen --size 512x342`. |
| MacPaint | Paints: the tools, patterns, brush shapes and line widths. Print Draft and Print Final print the picture to a PDF (see [Printing](#printing)). |
| Aliens | Plays. With `--host screen`, its playfield is the desk. |
| MacLanding | Plays, with `--host screen`, its radar drawn over the menu bar at the top of the screen, which it fills white, bar and all. |
| Frogger | Plays with `--host screen --size 512x342 --speed 1`. The keys are I, J, K and L, as capitals: hold Shift or turn Caps Lock on. |
| Airborne! | Plays, with its sounds, with `--host screen --size 512x342`: Start Game, and helicopters fly over dropping paratroopers. Holding the button down fires the gun toward the pointer, and hits score. |
| Crystal Raider | Plays, with `--host screen`. A click or key leaves the introduction for the Hall of Fame, and another starts the game. |
| MacWrite | Types and edits: lines wrap, Return starts a paragraph, and the Style menu's bold and italic work. Documents save, in either of the Save dialog's formats, and open again. Page Setup, printing and quitting work. |
| Microsoft Word 1.0 | Opens an Untitled document and types, with its lines wrapped at the margins. Selecting, the Character and Paragraph menus, the ruler and the Formats… dialog work. Saving and printing work. |
| Microsoft Word 4.0 | Runs, with `--app "Microsoft Word"`: opens an Untitled document and types, with its lines wrapped at the margins. Its menus work, and documents save, with Save As's own dialog, and open again. The Font menu cuts its sizes off at the right: Word draws its menus in a Chicago of its own, ".Word Chicago", but makes them as wide as Chicago measures, and without a Mac's ROM Chicago 12 is measured with your computer's font, which is narrower. |
| Microsoft Multiplan | Runs: click a cell to select it, then type a number or a formula, such as `=R1C1*3+1`, in the formula bar; Return enters it and moves down a row. |
| Font Mover (System 1.1) | Lists the fonts in the Fonts file next to it and shows a sample of the one picked, in the font's own bitmap, Cairo's pictures and all; Copy puts it in the System file. Help shows its two pages. macrt's own System has no bitmap fonts to list (see `--system`). |
| Disk Copy (System 1.1) | Says it works only on a 128K Macintosh, as it does on any later Mac. |
| Desk accessories (System 1.1) | With `--system` given System 1.1's disk, MacPaint's Apple menu lists them, and each opens in a window of its own: the Alarm Clock and the Control Panel show the date and time, Calculator calculates, Key Caps shows the keyboard and what's typed, Note Pad shows its notes, Puzzle slides its tiles and the Scrapbook shows its first page. |
| Microsoft Chart | Charts: type numbers in the New Series window's Y column and tick Plot Series to chart them. The Gallery menu's charts work, a pie with its percentages among them. |
| Microsoft BASIC | Runs programs: type lines in the Command window, then RUN; the output goes to Untitled. It reads about 15 keys ahead and beeps past that, as on a Mac, so the end of a long paste is lost. |
| MacDraft 1.2a | Draws: pick a tool in the palette, then drag in the drawing for rectangles, ovals and lines; the text tool types. |
| Lode Runner | Plays: Game > Start Game (Cmd-S), then the keyboard moves the runner (Options picks the keyboard or the mouse). With no game started it plays its demo. |
| Klondike 4.0 | Plays: OK the About box and press Play in the Scores window; click the stock to turn cards and drag them to the foundations and columns. |
| Rogue | Plays: name the character, then move with the keys h, j, k and l, or click where to go. |
| Fusillade | Plays: OK its introduction, then File > Play. I, J, K and L move; E, S, D and F shoot. On its MOOF image the game is the application named Finder, so give `--app Finder`. |
| ShufflePuck | Plays. Game > new game, then click to serve; the paddle follows the mouse, and swiping the mouse up the window hits the puck. Demo > play demo plays itself. |
| Dark Castle | Plays, with `--host screen --size 512x342`. Its launcher hands over to its Data A file, which shows the title screen; click it, and the Great Hall comes up, Duncan walking with the arrow keys. It draws each frame in one screen buffer while the other shows, and flips between them through the VIA. Its title screen plays Bach's Toccata in D minor, which it mixes into the sound buffer itself. |
| Flight Simulator 1.02 | Runs with `--host screen --size 512x342`, from its disk or its MOOF image (`--app "Flight Simulator"`): the cockpit, the view of Meigs Field and Chicago, the clock and the radios. Its own menus open from its menu bar, which is 10 pixels tall; the panel's switches answer a click held a moment, such as LIGHTS, or MOUSE CURSOR, which becomes MOUSE YOKE; and its keys reach it. It hides the pointer and draws its own cursor, which moves by how far the mouse moves, as on a Mac, so its cursor can stop short of an edge of the screen when the hidden pointer reaches the window's: move the pointer into the window's top-left corner and then its bottom-right, and the two line up. To fly, click MOUSE CURSOR to make it MOUSE YOKE: then the mouse is the yoke, and with the button held, moving it up and down works the throttle and side to side the rudder. |
| MacWrite 4.5 | Types, with the fonts, sizes, styles and alignments of its menus and ruler; Save As saves. It needs the default `--model plus`: it pops a 68000's exception frames itself. |
| SuperPaint 1.0 | Opens Untitled between its tool and pattern palettes, one window its own `WDEF` shapes, and draws with the tools and patterns. It keeps the Clipboard File in the System Folder, which macrt writes. |
| VideoWorks | Asks for its master disk: its copy protection, whose key track a raw 400K image loses. |
| Pyramid of Peril | Plays: Move Forward, Turn Left and Turn Right walk the corridors, and the map beside the view follows. |
| Psion Chess | Plays: click a piece, then the square to move it to, and the computer answers. Pick it with `--app "Psion Chess"`. |
| Grid Wars | Plays, with `--host screen --size 512x342`: click an opponent, then the ship follows the mouse along the bottom and a click fires toward the cross. |
| Wizardry I | Plays: drag characters from the Roster to the Party window, double-click Maze in The Castle and answer the stairs; then F moves the party forward and L turns it left. |
| Hitchhiker's Guide to the Galaxy | Plays: type commands at the prompt. Pick it with `--app "Hitchhiker's Guide"`. Release 47 plays from its MOOF image too, with `--host screen --size 512x342`. |
| Dungeon of Doom 5.4, The Dungeon Revealed | Play: click the title away, choose File > New Game… (New… in The Dungeon Revealed), name the character, press Onward! and name the saved game. Then click beside the hero to move. |
| Enchanted Scepters | Plays: type commands such as `look` or `go south` and press Return; the room's picture and text follow, in the frames its own `WDEF` draws. Cmd-I lists what you carry. |
| IAGO | Plays Othello: Start a Game, then click a square to move, and it answers. |
| Duane Blehm's games | Play; pick each with `--app`. StuntCopter: Begin, then the mouse flies the helicopter and a click drops the stuntman. CairoShoot: Game > Begin. ZeroGravity: click the Pod for free flight; the pilot then drifts the way the mouse is from (320, 239) on the screen, faster the further it is, and stops with the mouse there. PUZZ'L: Continue, File > Open "Cat Puzzle", then drag pieces from the strip to the board. |
| Space Invaders | Plays: click the Play box at the top right to start. |
| MacBASIC | Runs programs: File > New, type the program in its Source window, then Program > Run. |
| Gemstone Warrior | Plays: Gemstone Warrior > Start Beginner Game, and after the temple scene I, J, K and L move the warrior a step for each press. Options > Redefine Keyboard lists the keys, in the Chicago it brings, double arrows and all. |
| Déjà Vu | Plays: it opens on the Bathroom Stall, with the scene, its exits, the inventory, the command buttons and the story so far. Click a command, then what it acts on in the scene or the Exits window, and the story answers. It plays from its two MOOF images too, with `--host screen --size 512x342`. |
| Leisure Suit Larry | Plays: Return past the credits, click, type an age and Return, then answer the quiz by clicking the letters; the questions are picked at random. Then click to walk Larry, and type commands such as `look` and press Return. |
| The Oregon Trail | Plays: Travel the Trail, Continue, then type a name, pick an occupation and OK. Buy at Matt's General Store, Tab moving between the amounts, then pick a month, and Continue sets the wagon off along the trail. |
| Infocom's Masterpieces | ZORK I, ARTHUR, BEYOND ZORK and ZORK ZERO play: type commands such as `open mailbox` at the prompt, each followed by Return. Pick each with `--app`. ARTHUR shows its title picture until a key is pressed, then asks whether to restore a saved game (N); BEYOND ZORK wants BEGIN, then a character; ZORK ZERO draws its framed pages with their pictures, and a key turns past each [MORE]. The disk's TADS Run-Time 2.2 asks for a game in its Open dialog; the Winners folder has THE_ONE.GAM, TOONESIA.GAM and ZEBULON.GAM, and Toonesia plays, typed at its prompt. |
| SimCity 1.11 | Start a scenario: click Dullsville and click through its story to the city, its tool palette and the map. It then asks for a city's population from the manual's table, as its copy protection; a wrong answer is asked again. |
| Scarab of Ra 1.4 | Plays, with `--app "Scarab of RA 1.4"`: the arrows in the Movement window step and turn through the pyramid, and the view, the news, the inventory and the status follow. |
| SmoothTalker 2.1 | Opens Untitled and types. Speech > Speak Text speaks the text, through its own speech drivers, which write the sound buffer. |
| Wizard's Fire | Plays: Game > Start Game, and the missiles fall on the towns. MicroGames > Pressure and Brickbat, its own desk accessories, open in small windows of their own. With `--system` given the game's disk, Calculator opens from the Apple menu and works, by click or typed key. While a desk accessory is in front, the game passes its Game menu to it as the Edit menu, as on a Mac: click the game's window before Game > Quit. |
| Run for the Money | Plays, with `--host screen --size 512x342`: click past the introduction, then New Game and a skill level, and the two players' factories come up with their machines and cash. On its MOOF image, too, the game is named Finder: give `--app Finder`. |
| Make Millions | Plays, with `--host screen --size 512x342`: Play New Game, type a name and Okay, then click to start. The office's clock runs through the week, and clicking the telephone opens it, asking for a number. |
| ADVENTURE (James Associates) | Plays: answer its question about instructions, then type commands such as `look` and `go north` at its prompt, each followed by Return. |
| ][ in a Mac | Starts its Apple II: ProDOS 8's start screen, its keyboard and its disk drives. |
| Bird Race | Plays: click Race and the birds fly across the picture, at the odds beside them; the players' bets go in the table below. It reports "SpeechOn Error = -43" in the menu bar, as a Mac without MacinTalk does. |
| Social Climber | Plays: Game > Begin, then S and D walk the climber left and right; Game > Set Keys changes them. |
| Daleks | Plays: click an arrow beside the Doctor to move him that way, and the Daleks close in. The Game menu has Teleport, Last Stand and the Sonic Screwdriver. |
| Connect Four | Plays: click the oval above a column to drop a piece, and the computer answers. Game > NewGame starts again, with a few grey neutral pieces dropped at random, as the game does. |
| Brickles 7.0 | Plays: click to begin, and the mouse steers the paddle. |
| Microsoft BASIC 2 | Runs programs: type the program in the List window, then Run > Start; the output goes to Untitled, and the listing stays. |
| Skyfox | Runs with `--host screen --size 512x342`: its launcher chains to the game, whose title screen a click passes for the cockpit, its clock running, and a click on the cockpit's keyboard brings up the tactical map of the enemy's tanks. |
| Mac Attack | Runs with `--host screen --size 512x342`, from its MOOF image, and passes its copy protection, which times the disk turning under the head. Click, then click a level of difficulty, one to three stars, at the top of the screen, and the battle starts, its tanks, missiles and landscape drawn in the fonts its disk's System file has. Left alone, it plays its title and its attract mode. |
| Balance of Power: The 1990 Edition | Plays, with `--host screen --size 512x342`: New Game, then Start Game, and the world map comes up. Click a country to pick it; the Make Policies menu's dialogs then act on it. The title's letters are traced from the New York 36 the game carries, which macrt draws from rather than a host font. |
| Pirates! | Plays, with `--host screen`: click twice past the title, then answer its questions with clicks; any month answers its copy protection. The duel and the story follow. |
| Crystal Quest 2.2.5 | Plays, with its sounds, with `--host screen` and `--app "Crystal Quest"`: Return, then a click starts it, and the mouse steers the ship. With `--model ii --size 640x480` it plays in colour: it sets the screen to 16 colours through the video driver. |
| The Colony | Plays, with `--host screen`: click twice, then hold the button down to turn and press W to walk. |
| Cap'n Magneto | Plays, with `--host screen --size 512x342`: click Game, then the arrow keys walk. |
| Mac Missiles | Plays, with `--host screen`: click 1 Player, then click to fire at the missiles. |
| PhrazeCraze Plus | Plays, with `--host screen`: click through to Play, then Spin and pick letters. |
| Radical Castle | Plays, with `--host screen --size 512x342`: click Start. |
| Citgo, BackBay 2.0 | Show Kenmore Square. The first one's name starts with a space: `--app " Citgo"`. |
| Amazing | Plays with `--size 512x342`: the ball follows the mouse through the maze. The game sizes its maze from the screen but keeps it in arrays made for the original Mac's, so on a larger screen it runs past them and hangs on a grey screen. |
| The Quest | Plays, with `--host screen --size 512x342`. The disk holds no application, and the game took the Finder's place on it; macrt shows the disk in a Finder window instead, where a double-click on the game runs it. Press keys through the story, then type commands such as `n` at the prompt, or click the compass. |
| Prince of Persia | Plays: the introduction runs, with its music, Cmd-N starts the first level, and the arrow keys move the prince. |
| Glypha 3.0 | Plays: Cmd-B begins, then Space flaps and A and S steer (or ; and '). It needs a screen of 640x480 or more. Its disk has its sound off: Options › Configure Game turns it on. |
| Ishido | Plays, with `--app "Ishido (B&W)"`: Cmd-N deals, and a click places the stone in hand. |
| Battle Chess | Plays: click a piece, then the square to move it to, and it walks there; the computer answers. Its window needs a screen of 640x480 or more. |
| Kid Pix | Runs: its painting window, the tools and their options. |
| Macman Pro | Plays, with `--host screen`: Cmd-P starts it. |
| MacChess 2.0 | Plays, with `--model ii` and `--app "MacChess 2.0 EN"`: click a piece, then the square to move it to, and it answers, the move listed in its Moves window. On the default Plus it says it needs a 68020, as it does on a Mac. |
| Nigel's World 1.01 | Plays, with `--model ii --size 640x480 --app "Nigel’s World"`: its title picture, its palettes' colours, then Nigel's Home, its main screen, in its colours. The fax machine gives an assignment, a photograph from a continent, and the thumb up takes it: The World's map, naming the oceans under the pointer, counts the days left, the Klooculator sells clues, and Roxy's door opens on her office. |
| Spaceward Ho! 3.0.1 | Plays, with `--model ii --size 640x480 --app "Spaceward Ho! 3.0.1"`: it checks for 32-Bit QuickDraw's offscreen graphics, which macrt has. Type a name and an organisation, start a new game, save it where it asks, name the player, and the galaxy's window opens with its planets and fleets. Its pictures are black and white, with red for its licence text, as they are on a colour Mac. |
| Lemmings 1.5.2 | Plays, with `--model ii --size 640x480 --app Lemmings`: its title screen fades in, Lets Go gives the first level's briefing, and a click starts the level, the lemmings walking out, with the skills bar and the clock. |
| Pipe Dream | Plays, with `--model ii --size 640x480 --app "Pipe Dream™"`: a click past its title, then Start Game gives the first level's board, and clicks lay the dispenser's pieces. |
| Glider 4.10 | Plays, with `--model ii --size 640x480 --app "Glider 4.10"`: Return dismisses the two notes it shows at launch, and Game › New Game flies the glider into the first room. Its help, Glider Help, is in the Help menu, under the balloon at the right of the bar. |
| SimEarth (B&W) | Plays, with `--model ii --size 640x480`: a click past its title, and its World Map and Help windows open. File › New Planet offers its scenarios: Aquarium starts the planet's clock, reporting its events as they happen, and Windows › Edit shows the sea and its life. |
| Stratego 1.0 | Plays, in colour, with both its disks and `--model ii --size 640x480`. It asks to look for its colour pictures, the file Color Data 2: OK, then choose Desktop, Stratego Disk 2 and Color Data 2 in the dialog. A click past its title gives the board, with its Title and Piece Bin windows, which its own `WDEF` shapes, beside it; pieces drag from the bin onto your half of the board. The Level menu sets how well the computer plays. |
| Blockout 1.3 | Plays, with `--model ii --size 640x480`: a click past its title, then Start Game on its Main Menu and OK for the starting level, and the pit opens with a block falling into it; Space drops it. |
| Legends of the Lost Realm I | Plays, with both of its disks and `--model ii --size 640x480`: its title, then it asks where Gathering of Heroes is, the second disk: External Drive. Its Control, Status, Maze and Log windows open on the barracks. Click the Roster on the wall and drag a character from it into the Control window to take them into the party; Done, and the arrows walk the party out of the barracks. |
| MacGolf | Plays, from its raw image, on the default Plus: Continue past the Top Ten, Cancel when it asks to continue a saved game, Start Game, and pick a course, and the first hole comes up with the golfer, the hole's map, the wind and the club. Swing swings, and the strokes count. Its copy protection reads a sector through its own `RdData`, which reads only the data field's marks, so it reads one from a raw image's tracks as a Mac's format writes them (see [Disk images](#disk-images)). It draws the golfer straight into the screen as a Plus has it, so on a Mac II's screen he comes out as specks. |
| Math Blaster | Plays, with `--model ii --size 640x480`: a click past its title, then an operation, such as Addition, gives its activities and the level of problems. Look and Learn shows worked problems at the speed its scroll bar sets; Build Your Skill takes typed answers, Return entering each; and in Math Blaster!, once you've picked a speed, the acrobat follows the mouse along the cannons and a click fires him at the star with the answer, for points. |
| Reader Rabbit 2.0 | Plays, with `--model ii --size 640x480`: a click past its title gives its games, and the Sorter Game lays out its words for the rabbit to sort. |
| Speller Bee | Runs, and speaks, with `--host screen --size 512x342`, through the `.SAY` driver in its disk's System file (see [A real System file](#a-real-system-file)): it says its title and its question, and once it has finished speaking, No gives the menu of what to learn about. It saves and restores the screen as one block of a 512×342 Mac's size, so on a bigger screen its pictures come out torn. |
| The Slide Show Magician 1.2 | Runs, from its raw image, with `--host screen --size 512x342`: it checks for its master disk by reading its SHOW SUPPORT file through marks of its own (see [Disk images](#disk-images)). Run Shows, then DEMO SLIDE SHOW and Open, plays its demonstration show. |
| Jam Session 1.0 | Plays, with its sounds, with its three disks, `--host screen --size 512x342` and `--app "Jam Session"`: its two MUSIC disks, its songs and their instruments' sounds, are in the archive's zip. File › Open Song, then Desktop and MUSIC 1, lists the songs; one opens on its stage, and Jam › Play plays it, the band moving to the music. |
| Tetris | Plays, with its music, with `--host screen --size 512x342` and `--app TETRIS`: a click past its title, then Start Game. J and L move a piece, K turns it and Space drops it. Its colour version plays the same way with `--model ii --size 640x480 --app TETRIS.color`, in front of its colour pictures of Moscow. |
| Habadex | Runs, with `--host screen --size 512x342 --app HABADEX`: its directory and its appointments. New Record opens New Record Entry, and Tab moves from field to field. Its own arithmetic shows a year after 1999 with a symbol for the decade, 2026 as `<6`, as it would on a Mac. |
| Animation Toolkit I | Runs, with `--host screen --size 512x342`, from its DC42 image, whose sectors' tags its key-disk check reads: the Frame Editor, the untitled frames and the Animation Window. What the pencil draws in a frame shows in the Animation Window too. |
| ThinkTank 128 | Runs, with `--host screen --size 512x342`: an outline window, where typing writes a headline and Return starts the next. |
| MacCheckers | Plays, with `--host screen --size 512x342 --app Checkers`: drag one of the dark pieces, which move first, to the square ahead, and the computer answers, its Move Timer counting each side's time. |
| Mombasa 1.1 | Shows its board of tiles; a click picks one and names it. |
| BlackJack, Backgammon, Hearts 1.6 | Play. BlackJack deals once a bet is clicked; Backgammon sets out its board once its introduction is OKed; Hearts deals and asks for three cards to pass. |
| Missile Mac, MissileCommand 3.0, Mac Pong II, Mine Sweeper | Play. |
| Railroad Tycoon 1.01 | Plays: the arrow keys and Return (or clicks) choose through its setup, the area and the difficulty and reality levels, and the world builds in under a minute. It asks for a locomotive to be named, from the manual, and the railroad opens with RailNews Weekly and the map. |
| Shadow Keep 2.2 | Plays, with its sounds: a click goes into the game, and holding the button down walks the hero toward the pointer. |
| Castle of Ert, Pyramid of Ert | Play: click through the title (Pyramid of Ert has a Start the Game button), then type commands such as `n` or `look`. |
| Capitalist Pig | Runs to its copy protection, which asks for a figure from the manual's Appendix A. |
| BiPlane | Runs: OK its shareware notice, then click a cell and type. |
| DataFlow | Runs: pick a block from the palette and click in the DataFlow window to place it. |
| MineSweeper 1.3 | Plays, its opening sound first: once its notice has gone, pick a size from the Game menu and click squares. |
| Forty Thieves 2.1, Reversi, Surprise Avond | Play: Forty Thieves deals from its stock with a click, Reversi begins with a click, and Surprise Avond's puzzles (Anagrams, Arithmetic, Fifteen-A-Row and more) take clicks. |
| Frenzy | Plays: File > New game starts a round. |
| MacBugs! | Plays: MAC BUGS! > Start game, then click GO. |
| Microsoft Excel 1.0 | Runs from its original disk's MOOF image, which passes its copy protection, and opens Worksheet1. |
| FullPaint 1.0 | Runs: its tools, patterns and an untitled drawing. It decrypts its segments as they're loaded, through a patch on `GetResource`, and runs part of itself in the processor's trace mode. |
| Q-Sheet 1.0 | Runs from its key disk's MOOF image, which it reads through bits that read differently each time: a cue list, the track list and the SMPTE time. Its objects are Object Pascal's, through `_MethodDispatch`. |
| Dollars and $ense 1.3, PFS:FILE | Run from their key disks' MOOF images, which they read with data marks of their own through the ROM's `RdData`: Dollars and $ense to its title and menus, PFS:FILE to its New, Open and Quit choices. |
| Deluxe Music Construction Set | Runs: an untitled score and the piano keyboard. Version 2 runs the same from its MOOF image. |
| Macintosh Pascal 1.0 | Runs: type a program in its editor, which shows keywords in bold and indents as it goes, then Run > Check and Run > Go. `writeln` writes to the Text window and QuickDraw's calls draw in the Drawing window; a mistake brings up its bug alert. It draws and measures its program text through a port's own `textProc` and `txMeasProc`, and calls TextEdit's `TEDoText` routine itself. |
| PageMaker 1.2 | Runs, with both of its MOOF images (the application is on the second), and passes its copy protection, which steps the head a track in from its key sector and counts the bytes there as the disk turns. File › New, then OK in Page setup, opens a publication with its toolbox, whose icons are its own font's, a family numbered past 255. |
| The Home Accountant 1.01 | Runs, with `--host screen --size 512x342`, from its MOOF image, and passes its master-disk check: it asks whether to open an existing Home Accountant system or create a new one. |
| Microsoft File | Runs from its MOOF image and passes its master-disk check, which looks for a flag in two files' catalog entries. File › Open Datafile… opens the sample Good Restaurants, its records with their pictures, and Organize › Find… shows the form to search with. File › New Datafile… takes the new file's name in an edit text item of its Save dialog. |
| Lotus Jazz 1A | Runs, with both of its MOOF images (`00playable.moof` first) and `--app Jazz`, and passes its copy protection, which reads its key disk's bytes through the ROM's routines and times them with the VIA's timer as the disk turns them. File › New opens a worksheet that calculates, a word-processing document, a graph or a database. |
| The Print Shop 1.2 | Runs, with both of its MOOF images (`00playable.moof` first), `--app "The Print Shop" --host screen --size 512x342`, and passes its copy protection, which sets the IWM's mode to read its disk's last track. That track was never imaged, so the drive reads noise there and the program uses the key it stored when it was installed. Its menu offers Greeting Card, Letterhead, Banner and Sign; double-click one to open it, then pick a border and type the message. |
| Fontographer 2.4.1 | Runs, with `--host screen --app Fontographer`, from its MOOF image `00playable2.moof`. At launch it asks for a font: open DemoFont, from its disk, and it shows the font's characters in a window; double-click one to edit its outline. File › New Font asks for the font's attributes and opens Untitled-1. Generate PostScript writes the font and its AFM file to the disk in a few seconds. Generate Bitmaps stays dimmed. |
| PFS:REPORT | Runs from its MOOF image: open a PFS:FILE file from its disk, such as STAFF, and Count forms counts its forms. From its raw image (`00playable.dc42`, `--app "PFS REPORT"`) it runs to its Open and Quit choices. |
| MusicWorks 1.0 | Runs from its MOOF image: File › Open plays a song from its disk, such as Alla Turka, through the Sound Driver's four-tone synthesizer, its Overview's cursor going through the score. |
| Master Tracks Pro 1.10 | Runs, with `--size 640x480`, from its MOOF image, and passes its key-disk check, which it makes through the Sony driver's control calls. File › Open opens a sequence from its disk, such as Banana Shuffle, and Play counts its measures and beats with its own routine for the VIA's timer 1, which it puts in low memory's Lvl1DT. Its MIDI goes out through the serial chip (SCC), which macrt doesn't have, so it plays without a sound. Versions 3.4a and 4 run from their MOOF images too, with `--host screen --size 512x342`: each opens on its own installer's dialog, where Execute Original (3.4a) or Launch master (4) starts it. File › Open a song (3.4a's are in its Songs folder), and Play counts it in the same way. |
| Crossword Magic 4.0 | Runs from its MOOF image: File › Play… opens a puzzle from its disk, such as CHRISTMAS. It runs from its raw image (`00playable.dc42`) too, where File › New starts a grid. |
| The Toy Shop 1.1 | Runs, with its Master Disk and Toy Disks 1 and 2, the Master Disk first. The toy disks are in the archive's zip, not among its MOOF images. Its Catalog and Index show the toys; open one, such as the Carousel, and pick its paints. |
| The Fool's Errand 2.0 | Runs: its story opens on The Sun's page, and its menus, -I- to -V-, list the puzzles. |
| Beyond Dark Castle | Plays, with both of its disks, `--host screen` and `--app "Beyond Dark Castle"`: its title, the Great Hall, then Play takes the player into the Ante Room, read from the second disk. |
| Uninvited | Plays, with both of its disks and `--host screen --size 512x342`: its copy protection decrypts code it reads straight from the disk, and it finds its second disk through a volume control block of its own. Click past the introduction in the car, then pick a command and click an object or an exit: Open on the car's exit opens its door. It plays from its two MOOF images too, with `--app Uninvited`. |
| King's Quest | Plays, with both of its disks and `--host screen --size 512x342`: its copy protection reads a file with a damaged sector and counts on the File Manager's I/O error. Press a key past its credits, then type a command and Return (`look at castle`), or walk Sir Graham with the arrow keys. The game draws him and the room straight into the screen, in light dithers. |
| The Seven Cities of Gold | Plays with `--host screen --size 512x342`. Click past its title. Choose items by moving the mouse up or down and clicking. When it asks for the map disk, it ejects its own disk and gets it back. Pick an experience level. Then leave Spain's harbour and sail west from the Canaries with the arrow keys to land in the New World. |
| The Chessmaster 2000 | Plays, with `--host screen --size 512x342`: it opens on its board. Drag a piece to move it, and the Chessmaster answers; each side's moves and clock are listed beside the board. The game interrupts itself with its own copy of the ROM's handler, which calls the ROM's routines that low memory's Lvl1DT points at. |
| MacGammon | Plays, with `--host screen --size 512x342`, from its MOOF image, and passes its copy protection, whose own copy of the ROM's routine reads its key sector and decodes the disk's bytes through the ROM's table at A3. Click START, then File › Start Game: the cups roll for who goes first, the roll shows under the board, and the checkers move. |
| Archon | Plays, with `--host screen --size 512x342`, from its MOOF image: click past its title for the Strategic Board. Click one of Light's pieces, which the game names, then the square to move it to, and the computer, playing Dark, answers. |
| Mouse Stampede | Plays, with `--host screen --size 512x342`, from its MOOF image: One Player, then Start, and the mice wind down through the cheese. The mouse steers the shooter and its button fires. |
| Sargon III | Plays, with `--app "Sargon III" --host screen --size 512x342`, from its MOOF image: drag a piece and Sargon answers, the moves listed in its PLAYER/SARGON window. It drags its pieces with `DragTheRgn`. From its raw image (`00playable.dc42`) it quits at once: it doesn't pass its key check there. |
| Shadowgate | Plays, with both of its disks and `--host screen --size 512x342`. Its second disk is in the archive's zip, not among its MOOF images. Click to continue through the opening text, and the command buttons come up. |
| Zork I, Zork III, Deadline, The Lurking Horror, Planetfall, Stationfall, The Witness, Ballyhoo, Spellbreaker, Nord and Bert | Play, with `--host screen --size 512x342`, from their MOOF images: type a command and Return (`open mailbox`, `read leaflet`), and the score and moves update. When the opening text fills the window, the interpreter waits for a key before it goes on, and that key isn't typed at the prompt. Nord and Bert opens on a list of its stories: type one's name to go to it. |
| Shanghai | Plays, with `--host screen --size 512x342`, from its MOOF image: click two matching tiles to take them away; a mismatch says so. |
| Arkanoid | Plays, with `--host screen --size 512x342`, from its MOOF image. Click for its Start New Game dialog and pick One Player Start. After its introduction it asks for the round to start on, which moving the mouse changes. |
| Oids, Tesserae | Play, with both of their MOOF images (the application is on the second) and `--host screen --size 512x342`: Oids' Play warps to the Cosmoids galaxy, and Tesserae's Start opens its picker of mosaics, with its sounds. |
| Squire 1.1 | Plays, with `--host screen --size 512x342`, from its MOOF image: press P, and Return at its list of players, and it asks for your initials. Type them and press Return, then Return again: it says Creating a new game for about 30 seconds, then shows its MENU SELECTION. B lists the investments, and a number shows one of them (Blue Chip Stocks, with their prices) to buy from; M shows a graph of the General Economy, and Space goes back to the menu. |
| Pinball Construction Set | Runs, with `--host screen --size 512x342`, from its MOOF image: its editor, where parts drag from the box onto the table. |
| Falcon | Plays, with both of its MOOF images (`00playable.moof` first) and `--host screen --size 512x342`. Its first application plays the title, then Launches the game on the other disk by its full pathname, `Falcon 2:Falcon`, and the game opens on its Duty Roster. Sign on with a name, take a mission (Milk Run), and after its ARMAMENT and TAKEOFF screens it puts you in the F-16's cockpit on the runway, with the HUD, the radar map and the instruments. W releases the wheel brakes and = opens the throttle into afterburner, and the airspeed climbs on the HUD; hold the keypad's 2 to pull the nose up and it leaves the runway, the HUD's heading and altitude changing. |
| Winter Games | Plays, with `--host screen --size 512x342`, from its MOOF image. Click past its title and its opening ceremony to its menu: Practice ONE Event lists the six, and each plays: Hot Dog, Biathlon, Figure Skating, Ski Jump (click at the end of the ramp to jump), Free Skating and Bobsled. It makes a heap zone of its own with `InitZone`, and draws each event's scenery from a picture file through a `getPicProc`, in a handle it has unlocked: `DrawPicture` reads the picture's frame before anything can move it. |
| The Ancient Art of War | Plays, with `--host screen --size 512x342`, from its MOOF image. Game › Go to War lists its campaigns: double-click one, then Done › Continue past its briefing, rules and choice of opponent to the battlefield. Its check of its original disk counts the bytes on a track whose bytes are written four zeros apart. |
| Hacker | Runs, with `--host screen --size 512x342`, from its MOOF image, past its copy protection: type at its LOGON PLEASE: prompt and press Return, and the system you've reached answers (`? LOG-F-SYNTAX ERROR`). |
| Hacker II | Runs, with `--host screen --size 512x342`, from its MOOF image. It dials for about 20 seconds before its LOGON PLEASE: prompt: type HELP and Return for its terminal's commands, or a name and Return, and ACTISOURCE's hotline answers. It types its text a letter every few ticks, waiting for the Ticks to change and then looking for a key with `GetNextEvent`, which returns at once when it has nothing to give, as on a Mac. |
| The Duel: Test Drive II | Plays, with `--host screen --size 512x342`, from its MOOF image: its title, top scores and RACE AGAINST menu, its skill levels, and a race against the clock in its Ferrari's cockpit, with the scenery, the rear-view mirror and the gauges. It looks for its disk in the drive queue, to tell a floppy from a hard disk. The arrow keys drive, or the keypad's 8, 2, 4 and 6: Up speeds up, Down brakes, and Left and Right steer down the road, past its traffic and its speed limits. |
| Shufflepuck Cafe | Plays, with both of its MOOF images (`00playable.moof` first) and `--host screen --size 512x342`, past its copy protection, and opens in the bar with the Current Champion on the board. Its own routine reads a key sector as the floppy controller shifts the bits in, and partway through a byte it stops the shifting for as long as its own instructions take. The bytes after are its key only if as many bits go by unread as would on a Mac. |
| Ferrari Grand Prix | Plays, with `--app "Ferrari Grand Prix" --host screen --size 512x342`, from its MOOF image: give a name for its Famous Drivers and a level, then OK, and its cockpit comes up on the track, with the laps and times below. Game › Start Race… asks for the number of laps (click OK: Return doesn't take it); then press the mouse button, and the light at the top left counts down. When its bottom light comes on the others pull away: hold the button down to accelerate, press 1 for first gear and 2–5 for the others (Game › Keyboard Assignments lists the keys), and move the mouse left and right to steer. The lap clock runs and the speed shows next to the revs. Game › Practice drives the same way without the light. |
| Déjà Vu II | Plays, with `--app "Lost in Las Vegas" --host screen --size 512x342`, from its MOOF image. It opens as Déjà Vu does, in the Bathroom, with the story so far and its inventory, Exits and command windows. |
| Dragonworld | Plays, with both of its MOOF images (`00playable.moof` first) and `--host screen --size 512x342`, past its copy protection. After its credits it shows the story and the city of Kandesh while its music plays, then its title: press G to start, any key past `<MORE>`, then type a command and Return. Its own routines find a key sector and count what its key track has. |
| Temple of Apshai Trilogy | Plays, with `--host screen --size 512x342`, from its MOOF image. It has no Apple menu. Click past its title; Character › New Character, then CREATE, rolls a character to name. Game › Temple of Apshai asks which level, and the first room comes up beside the character's wounds and fatigue. Type a number to move that many steps; the BATTLE and SPECIAL menus, or the letters they list, fight and search. |
| Where in Europe Is Carmen Sandiego? | Plays, with both of its MOOF images (`00playable.moof` first) and `--host screen --size 512x342`. Click past its title, and its robot scans for about 20 seconds before it asks for your name: type it and Return, and answer its question with y or n. The Chief calls with the case, and the chase starts in the city of the crime, with its clues, the travel and investigation icons and the crime computer. |
| Sub Battle Simulator, GATO, Strategic Conquest | Play, with `--host screen --size 512x342`, from their MOOF images: Sub Battle's status report and periscope, GATO's control panel and gauges, Strategic Conquest's map and its Game Set-Up. |
| The Pawn, Tass Times in Tonetown, Borrowed Time, Transylvania | Play, with `--host screen --size 512x342`, from their MOOF images (The Pawn has two): type a command and Return. Tass Times and Borrowed Time show their pictures, and Transylvania asks you to sign its guest register. |
| Wizardry II, Alter Ego, Bridge 6.0, Mac Vegas, Patton vs. Rommel, One on One, Star Trek: The Kobayashi Alternative | Run, with `--host screen --size 512x342`, from their MOOF images: Wizardry II's Castle and Roster, Alter Ego's New Game (both its male and female disks, each started by its launcher, which leaves the Finder information for the game to read), Bridge's opening deal, Mac Vegas' table of games, Patton vs. Rommel's choice of side, One on One's court and Star Trek's orders. |
| Apache Strike | Plays, with `--host screen --size 512x342`, from its MOOF image: Play, and after its briefing the Apache flies down the city's streets, with its radar, gauges and score beside. It draws its flight where a Mac Plus has its two screens, at the top of 4 MB, and flips between them through the VIA; here those addresses are the 512x342 screen's. It starts its engine's sound, of over two minutes, with an immediate write to the Sound Driver, which doesn't wait for it to end. |
| Frogger, Defender of the Crown, Mindshadow | Play, with `--host screen --size 512x342`, from their MOOF images: Frogger's buttons start a game, and Defender of the Crown tells its story in Sherwood Forest and has you choose a character. Mindshadow asks for 1 or 2: press 1 twice, as the first goes by while its Activision screen waits, and it opens on its beach, where you type a command and Return or pick from its Verbs and Nouns. |
| Indiana Jones and the Last Crusade | Runs, with both of its disk images (the System disk, `00playable.dc42`, first) and `--host screen --size 512x342`: the Lucasfilm Games logo, its title and credits, then Escape skips to Barnett College, and a click takes Indy indoors to Marcus. Its window covers the whole screen, the menu bar too, as it puts the bar back in its window's visRgn itself. |
| Fokker Triplane Flight Simulator | Plays, with `--host screen --size 512x342`, from its MOOF image. Pick a flight from the Game menu, Touch'n Go's, Dogfight or Self Fly, then click in the cockpit to take off: the mouse is the stick, 2 and 1 change the throttle, Space fires and Backspace ends the flight (Game › Change Keys changes them). With `--system` given the game's disk, the Scrapbook in the Apple menu holds its help pages. Game › Help opens the fourth item of the Apple menu, which was the Scrapbook on a 512K; here it's the Calculator, as a Mac Plus lists desk accessories in alphabetical order. The game moves its globals (its A5 world) below $70000 before it calls `InitGraf`, and desk accessories find QuickDraw's globals there. |
| Goldfinger, The Mist, Rambo, Forbidden Castle, Indiana Jones in Revenge of the Ancients | Play, with `--host screen --size 512x342`, from their MOOF images. Each disk has Angelsoft's MiniFinder and the game's own program beside it, so name the game with `--app`: `Goldfinger`, `"The Mist"`, `Rambo`, `Forbidden` or `"Indiana Jones™*"`. The story comes a window at a time, (MORE) between, then type a command at the `->` prompt and press Return. |
| A Mind Forever Voyaging, Trinity, Border Zone | Play, with `--host screen --size 512x342`, from their MOOF images: type a command and Return. Border Zone asks first which of its three chapters to play. |
| Fraction Action, MathTalk, KidTalk | Run, with `--host screen --size 512x342`, from their MOOF images, past their copy protection, whose key track reads differently each time it's read (see [Disk images](#disk-images)): Fraction Action's story of the mad professor's mansion, then How many Players?; MathTalk's NEW USER and MAIN MENU; KidTalk asks whether you've used it before. |
| Physics 1.2 | Runs, with `--host screen --size 512x342`, from its MOOF image: a dialog of its chapters and their lessons, and a lesson that draws and animates, as Vectors' arrow does. |
| MacWars | Plays, with `--host screen --size 512x342`, from its MOOF image: the starfield and crosshairs, with shields and score. |
| Alternate Reality: The City, Where in Time Is Carmen Sandiego?, The Crimson Crown, Harrier Strike Mission I and II, HardBall, Earl Weaver Baseball, Championship Star League Baseball, Smash Hit Racquetball, MacMatch, Maze Survival, Millionaire, Murder by the Dozen, OrbQuest, Pensate, Speed Reader II | Run, with `--host screen --size 512x342`, from their images (Alternate Reality's program is `--app Start`): Alternate Reality draws its city; Carmen Sandiego's ACME Detective Agency and its elevator; The Crimson Crown's lake shore with its buttons and text; Harrier Strike Mission's missions and cockpit gauges; HardBall's game options; Earl Weaver Baseball asks for the season ticket pass number of a seat it names; Star League Baseball's mode menu; Racquetball asks for your name; MacMatch's title and menus; Maze Survival's skill levels; Millionaire's player directory; Murder by the Dozen's twelve cases; OrbQuest's story; Pensate's board and pieces; Speed Reader II's exercises. |
| Sierra Championship Boxing | Plays, with `--host screen --size 512x342`, from its MOOF image. Information › Choose Boxers… lists them: OK its instructions, click a boxer for each corner and OK. OK the Tale of the Tape and the rules of the fight, then Options › Begin the Fight, and they box while the round's clock counts down. |
| Vegas Video Poker | Plays, with `--host screen --size 512x342`, from its MOOF image: Return past its index, then R, and A for machine A. Return bets $5; type the numbers of the cards to hold, and Return draws. |
| Geometry, Fast Break, The Mind Prober | Run, with `--host screen --size 512x342`, from their MOOF images (Geometry has two, `00playable.moof` first). Geometry opens on a dialog of its chapters, and Subject › Chap. 1 opens Points, Lines, Planes. Fast Break's menu has three rows: W and X move between them, and Tab changes the highlighted row, either the quarters' length or who plays (two players by default; `-C-` marks the team the computer takes). Space starts a game only when "(SPACE) TO START GAME" is highlighted. A second Space goes past the rosters to tip-off, and the game and shot clocks run. Player one steers with Q W E / A S D / Z X C and uses Tab as the button. Left alone for about 25 seconds, the game plays itself as a demo with the clocks stopped, until either player moves or presses their button. In The Mind Prober, File › New Subject… asks for the subject's initials, and OK starts its questionnaire, PROBING YOUR SUBJECT. |
| The King of Chicago | Plays, with `--app "The King" --host screen --size 512x342`, from its MOOF image. Its only menu is Projector: Start the Show, and Pinky thinks in balloons. Click one to choose what he says. |
| Downhill Racer | Plays, with `--host screen --size 512x342 --speed 1`, from its MOOF image: from the lodge to the slope, where the mouse steers. At that speed its title comes up after about 12 seconds, and its skiers after about 18. It divides by the ticks its first frame took to draw, which on a Plus is at least one, so without `--speed` it stops with a zero divide (system error 4). Its copy protection reads its key track with its own RdData, which is called with interrupts masked, as the Disk Driver has them. To make the interrupts it doesn't want do nothing, it looks past Dequeue's code for the ROM's next RTE, and then gives up if the Time has moved on 3 seconds: there's an RTE soon after the traps' code, as in the ROM. Its sounds are the Sound Driver's queue at SoundDCE, which its StartSound glue changes. |
| Wizardry VI: Bane of the Cosmic Forge | Runs, with its six disks, `--app Bane --host screen --size 512x342`, from its MOOF images, to its Master Options. It ejects and unmounts its first disk and asks for disk B: choose `Bane "B"` in the dialog, Insert, and press Return. Press a key at its title, and it asks for disk A again: choose `bane a`, Insert and Return. Its Master Options are Resume Saved Game, Character Menu and Quit Game. Return there asks for the magic word for three icons, which its manual gives. |
| Moebius: The Orb of Celestial Harmony | Runs, with `--host screen --size 512x342`, from its MOOF image, past its copy protection, to its title and the story after. Return goes on to The Book of Moebius: click Go to current adventure, then the disciple already on the disk, Jody, and the adventure opens on Earth, with the days, food, water and shurikens counted. The check finds sector 0's address field on a track, steps the head a track in through the drive's own registers, waits through the ROM's WakeUp for the head to settle, and expects sector 2 to be the next to come round. That holds only if the step and the settling took between about 37 and 50 ms, as on a Mac. |
| The Surgeon | Runs, with `--app Surgeon --host screen --size 512x342`, from its MOOF image, past the routine that decrypts its code in trace mode, to the check of its master disk, where it asks for the Master Disk. The check times eight marks on track 4 with the VIA's timer against a table of what they took on its own disk, each to within about ten ticks. On the image's track, the seventh mark comes about nine bits late against the sixth and the eighth. A bitstream keeps a track's bits but not how long each took, so it can't show a stretch the duplicator wrote faster or slower than the rest. archive.org's note on the image says the game fails its check in archive.org's in-browser emulator too, and passes in MAME run locally. What MAME does differently isn't known yet. |
| ][ in a Mac | Runs, with `--host screen --size 512x342`, from its MOOF image. It's an Apple II emulator, which draws the Apple's screen straight into the Mac's screen memory, and it boots the Apple DOS 3.3 disk that comes with it to its menu. Press 2 for Applesoft BASIC: type a program and `RUN` it, `CATALOG` lists the disk and `HGR` draws in high resolution. `RUN LITTLE BRICK OUT` plays: Options › Use Joystick makes the mouse the paddle and a click its button, and Command-click gives the mouse back. |
| Mac Pro Football | Plays, with both of its disk images (the game's, then Team Files), `--app MSFL --host screen --size 512x342`. MSFL is the game, a program for Microsoft BASIC's run-time, which is launched with it (see [Opening a document](#opening-a-document)). Click past the credits, then New game and a style of play, such as Head up vs. computer. It asks for the visiting team, then the home team: click Desktop, then Team Files, the second disk, and a team. Then pick each team's quarterback, the weather and the coin toss, and choose the kickoff: the play runs, with the clock and the teams' stats. Its play by play goes to the printer port, which has nothing plugged in. |
| Moriarty's Revenge | Plays, with `--app "Moriarty's Revenge" --host screen --size 512x342`, from its disk image. Its code is encrypted, and its patch on GetResource decrypts each segment as it's loaded. Click past its quotes and title to Scotland Yard: Join Irregulars, Where Do I Sign, and fill in the form, Return after each line. Then Ready for a Case, the agent's tab, Looks Good and Team Assembled, and click The Game's Afoot! once the visa has scrolled in: the case opens in Dacca, with its places to search and the cities to fly to. |
| Hidden Agenda | Plays, with `--host screen --size 512x342`, from its disk image. Begin opens the form to sign in: type your first and last names and your mother's maiden name, Tab between them, then Return. At the press conference, click the box that matches your views on each question, and the first year of your presidency begins. |
| Feathers and Space | Plays, with `--app Finder --host screen --size 512x342`. The game is the disk's Finder; Boot Configure, the disk's only application, isn't the game. Click for the menus: File › Play Game asks for a name for the high scores and plays the first wave. |
| Scarab of Ra | Plays, with `--app "Scarab of RA 1.4" --host screen --size 512x342`. The arrows in its Movement window walk the pyramid's corridors, and walking forward earns prestige. |
| The Colony, Frankie's Dungeon, The Lawn Zapper, Mac Missiles | Play, with `--host screen --size 512x342`. The Colony crash-lands its ship and opens on its rooms in 3D wireframe. In Frankie's Dungeon, Play opens the forest. The Lawn Zapper's One Player goes through Get Ready to the lawn. Mac Missiles starts after a click and 1 Player. |
| Pararena | Plays, with `--app "Pararena 1.3" --host screen --size 512x342`. Game › Begin starts a game, and its menus choose Which Game, the Opponents and the Options. |
| Pirates! | Plays, with `--host screen --size 512x342`. Click past its title. Return doesn't pick its options, so click them: start a new career, then the historical period, nationality, name and Continue, the difficulty and a special ability. "Young and poor…" begins the career. |
| Railroad Tycoon | Plays, with `--app "Railroad Tycoon 1.01" --host screen --size 512x342`. Return goes through Start New RR, Select Area, "Are you an…" and the Reality Levels, and then it generates the map. |
| Skyfox | Plays, with `--app skyfox --host screen --size 512x342`. Click its title, then Click Here to Start Mission for the tactical map. Return goes to the cockpit, LAUNCH WHEN READY. |
| Wishbringer | Plays, with `--app Wishbringer --host screen --size 512x342`: Return at MORE, then type commands. |
| Race Car Simulator | Plays, with `--memory 384 --host screen --size 512x342`. It's a MacFORTH program, and its SIZE resource asks for 96K, too little for its FORTH dictionary. Without `--memory` it stops at MacFORTH's prompt, "EXTEND ? ok". Click Here to Start, then Options › Start Practice Run. Hold the button with the pointer in the steering box, the strip across the bottom of the driver's view, to accelerate: where the pointer is in the box steers, and Space brakes. |
| Professional Composer 2.3 | Runs, with both of its disk images (`00playable2.dc42`, the program's, first), `--app "Composer™ 2.3Mfx" --host screen --size 512x342`. OK its MIDI Interface dialog, and its menus work. |
| Ford Simulator II | Plays, with `--host screen --size 512x342`. Main Menu › Driving Simulator, then Start Game › Start: it says you're about to begin driving at the BEGINNER level, and its first event is a drag strip, where the gears are changed by hand. Hold the mouse button down to accelerate and press E to shift up a gear (R shifts down); at the end it gives the score and the average speed. |
| The Lüscher Profile | Runs, with `--app "The Lüscher Profile" --host screen --size 512x342`. Profile › Take the Test asks for a name, then says to turn to TEST 1 in your Test Booklet. |
| HyperCard 1.2.2 | Runs, with `--app "HyperCard 1.2.2" --host screen --size 512x342`, from the Culture disk image, which opens on the disk's stack. Its menus and stacks work: Command-M opens the message box, where `put 3+4*10` gives 43, and the Go menu reaches the Home stack's User Preferences. |
| The Manhole | Plays, with HyperCard's disk after its own, `TheManhole.img Culture.img --app "the Manhole" --host screen --size 512x342`. The stack is a document, which HyperCard opens (see [Opening a document](#opening-a-document)). It opens on the manhole, with a beanstalk growing out of it: click where to go. |
| Cosmic Osmo | Runs, with `--app "Cosmic Osmo" --host screen --size 512x342`. Its title is the plane: click its side to open the hatch and the hatch to go in, to the lounge and on to the cockpit. |
| Maelstrom 1.4.3 | Plays, with sound, on a colour Mac II, `--model ii --depth 8 --app "Maelstrom 1.4.3 ƒ:Maelstrom" --host screen`. Click Not Yet on its shareware notice; its main menu shows the high scores, and P starts the game, full screen. It mixes its sound itself and plays it with SndPlayDoubleBuffer. |
| Jetpack | Plays, in colour, with `--model ii --depth 8 --app Jetpack --host screen`. It needs a 68020 or later. Its title and high scores come first, then its demo; File › New Game (Command-N) starts a game, and keypad 8 fires the jetpack while keypad 4 and 6 move left and right (Options › Controls changes them). Options › Music Volume is a hierarchical menu. |
| Crystal Crazy | Plays, with `--app "Crystal Crazy™" --host screen --size 512x342`. Click to start a game; Return shows the instructions and H the high scores. |
| Spelunx | Runs, with `--app " Spelunx " --host screen --size 512x342`, the name with a space either side. It's a HyperCard 2 stack built as an application. OK the alert that Palatino is missing, and it opens on its main screen of pictures, with the menu bar hidden. The first picture goes to the cave's entrance: click the door to open it and go in. |
| Bolo | Plays, with `--app "Bolo 0.99.7" --host screen --size 512x342`. Choose Practice in its Network Selection and OK, then OK its Game Setup: it shows the game's view of Everard Island. Its Tutorial teaches the game a step at a time: hold Q, and the tank's boat goes up the river, then the tank drives on over the grass and into the forest. |
| BMAPEdit 4.0 | Runs, from the same disk, with `--model ii --depth 8 --size 800x600 --app "BMAPEdit 4.0"`. It wants System 7 (Gestalt's Help Manager, PPC Toolbox and `LaunchApplication`), which macrt says it has. Return closes its shareware notice; File › New opens an Untitled map with its tool palette and its View Options and Draw Options windows, whose sliders are its own `CDEF` and whose title bars its own colour `WDEF` draws. BMAPEdit 1.2, on the 500 Mac Games CD, gets to its map, tile palette and tools too: the routine that makes its black-and-white start square ends with `SetPort` and no result of its own, so it returns whatever is in D0, which macrt leaves 0 after a Toolbox routine that has no result. |
| Citadel | Plays, with `--host screen --size 512x342`. Type a name at its request for one and press Return; its title and introduction follow, then a click goes on to the town, whose signs name its places. A click on a sign says what it's for, and a double-click goes there: the Tavern, where a party is formed, has Done and Carouse. |
| Rescue!, Action-Strategy Baseball, CX Base 500, My Office, Seastalker, Mavis Beacon Teaches Typing 2.0, Spaceway 2000 | Run, with `--host screen --size 512x342`, to their first screens: Rescue!'s title (`--app "Rescue! 2.0.5"`), A-S Baseball's teams, CX Base 500's window, My Office's alert that it can't find the last file used, Seastalker's request for your first name, Mavis Beacon's Enroll and Sign In (`--app "Mavis Beacon™ 2.0"`) and Spaceway 2000's story (`--app "Spaceway 2000™"`). |
| Shanghai II: Dragon's Eye | Plays, with `--app "Shanghai II-Dragon's Eye:Shanghai II" --host screen --size 512x342`. OK its dialog to personalize your copy, and it lays out the Dragon. |
| Darwin's Dilemma, Icon Quest | Play, with `--host screen --size 512x342`, from the one disk: `--app "Darwin's Dilemma 2.0.1.1:Darwin's Dilemma 2.0.1"`, then Play, shows the board with its score, level and swaps, and `--app "Icon Quest:IconQuest 1.21"` its board of icons. |
| Sargo Noidz | Plays, with `--host screen --size 512x342`. Return starts the pawns marching down the board, and the arrow keys move your piece. |
| Toxic Ravine 2.0 | Plays, with `--app "Toxic Ravine 2.0" --host screen --size 512x342`. Type a name, then Game › Start Game fills the ravine with barrels under the balloon, and the panel beside it launches the robot and the smart bomb. |
| MacRacquetball | Plays its demo, with the 4am crack's image and `--app "MacRacquetball™" --host screen --size 512x342`: Demo on its control panel plays on the 3D court. It relaunches itself until the top of memory leaves room for a second screen. |
| Halloween Night II | Plays, with `--app "Halloween Night II (message)" --host screen --size 512x342`. OK BugByte's message, and it shows the house at night; click to go in. |
| Monopoly 3.13 | Plays, with `--app "Monopoly 3.13" --host screen --size 512x342`: its title, how many players, then the board, asking each player's name and its house rules. Commands › Roll Dice rolls and moves the token, and offers the lot it lands on; Click Here To Continue goes on to the next player, and Status › Player Stats lists where each player is and their money. |
| The Hobbit, The Fellowship of the Ring | Play, with `--host screen --size 512x342`, from the Tolkien disk: `--app "The Hobbit:Hobbit"`, then New Game, Pictures and Start Game, shows the hall's picture and text, and `--app "The Fellowship of the Ring:Part1"` the burrow's, where you are Frodo. |
| 3 in Three | Plays its story, with `--app "3 in Three™" --host screen --size 512x342`: click to continue (in its menu bar) from one cartoon to the next. |
| Dubbelmoral! | Runs, with `--app "Dubbelmoral! ƒ:Dubbelmoral!" --host screen --size 512x342`. It's in Swedish: the town's map, the Nile and the status window. |
| PicottHouse | Plays, with `--app PicottHouse --host screen --size 512x342`. Click the front door to open it and go in. |
| SimpleText, Note Pad, Stickies, Jigsaw Puzzle, Scrapbook, Find File | Run, from PicottHouse's disk, which has System 7.5.3, with `--model ii --depth 8 --size 640x480`. `--app SimpleText` opens an untitled document to type in; `--app "System Folder:Apple Menu Items:Note Pad"` opens its first page, and `Stickies` (in the same folder) a note, both to type in; `Jigsaw Puzzle` shows its puzzle of the world, `Scrapbook` an empty Scrapbook and `Find File` its window for what to find. Find File reads Apple Event Manager globals that macrt doesn't keep, through the ExpandMem pointer at $2B6, which macrt leaves at 0, so the pointer it follows there is made partly of the random seed at $156, which is set from the clock when the machine starts: started at some times it opens its window, at others it stops with a bus error. Their resources are compressed with the disk System's `dcmp`s, and they look for System 7.5 (see [A real System file](#a-real-system-file)). |
| Desktop Patterns | Runs, from the same disk, with `--model ii --app "System Folder:Control Panels:Desktop Patterns"`. Its scroll bar goes through its patterns, and Set Desktop Pattern paints the desk in the one showing (`PaintOne` with no window, or `SetDeskCPat` for a colour pattern). They're its black-and-white ones, as the parameter RAM macrt starts with says the desk's pattern is. |
| ResEdit 2.1.3 | Runs, in colour, from a disk with System 7.5.3 and Toxic Ravine, with `--model ii --depth 8 --size 640x480 --app "ResEdit:ResEdit"`. Click its startup screen away for its Open dialog, with its own New button and alias check box. Open a file (About ResEdit 2.1.3, beside it) for its resource types, a type for its resources and a resource for its editor, such as the picture editor. |
| Script Editor | Opens, from the same disk (`--app "Apple Extras:AppleScript™:Script Editor"`), with an untitled script, but Check Syntax and Run say it can't connect to the scripting system. AppleScript is an extension, which macrt doesn't run, so there's no scripting component for Script Editor to open. |
| Apple Video Player, AppleCD Audio Player | Run, from the same disk (in Apple Extras), as far as the alert each shows: that there's no video hardware, or that the CD-ROM drive isn't responding. macrt has neither. |
| Fantasy Quest | Plays, with `--app "Fantasy Quest:Fantasy Quest" --host screen --size 512x342`. Click the title away, and it shows the first room's description and its Commands and Weapons menus. |
| Hextris, Snakes Alive | Play, with `--host screen --size 512x342`: Hextris's File › New, then the arrow keys move the piece; Snakes Alive's File › New Game, then A, Z, comma and period steer the snake. |
| Cantattain II | Plays, with `--host screen --size 512x342`: Options › Play shows the platforms and ladders, with the score, bombs, lives, level and round. |
| HyperQuest, Tiny Tim | Play, with `--host screen --size 512x342`: HyperQuest (`--app HyperQuest-1.03`) is a stack that the HyperCard 1.2.5 on its disk opens; click past its title to the Entrance Tunnel. Tiny Tim (`--app "Tiny Tim"`) opens on Hake's Grocery; click to go in. |
| NetTrek | Plays, with `--app "NetTrek-The Real Version:NetTrek" --host screen --size 512x342`: Continue its alert that AppleTalk is inactive, then Play, for the viewscreen, the scanner and the controls. On a Mac II in colour (`--model ii --depth 8 --size 640x480`), it draws each side's ships in its colours. Its menu title shows "NetTrek89012" in place of its logo, which it draws by patching `DrawString`: macrt's menu bar doesn't call it. |
| Theldrow | Plays, in colour, with `--model ii --depth 8 --size 640x480 --app "Theldrow Folder:Unnamed" --host screen`: the saved character opens Theldrow. Click the title, then Onward, for the character sheet, the 3D view and its description. The Magic, Cleric and Components menus, which its own `MDEF` draws in its font, cast spells. |
| Foo Castle | Plays, in colour, with `--model ii --depth 8 --size 640x480 --app "Foo Castle: Foo Castle" --host screen`. It's a MacroMind Director projector: click through its titles, and the castle's door zooms in and opens on the entryway. |
| Pico 2.0 | Works, in colour, with `--model ii --depth 8 --size 640x480 --app "Pico2.0 Folder:Pico 2.0" --host screen`. Type an expression in its editor (`x*y` draws a moiré) and choose Image › Execute; Image › Load Image… loads a PICT, such as "steve" on its disk, for expressions such as `steve[X-x,y]` to use. |
| MacJack 3.0.1 | Plays, with `--host screen --size 512x342`: give a name for Casino Credit, then drag chips from the bankroll onto YOUR BET and click the deck, and the hands are dealt, with Insurance? when the dealer shows an ace. |
| Dali Clock | Runs, with `--host screen --size 512x342`: `--app "Dali Clock (Original)"` and `--app "Dali Clock (Ephraim)"` show the time in their big digits, which melt from one second to the next. |
| Xyphus, PENSATE, Transylvania, The Crimson Crown | Run, with `--host screen --size 512x342`, from the Penguin Software disk: `--app "Xyphus:Xyphus"` opens on its first scenario's story beside a character's sheet; `--app "PENSATE™ ƒ:PENSATE™"` on its board and controls; Transylvania (`--app "Transylvania:Transylvania"`) and The Crimson Crown (`--app "Transylvania 2:The Crimson Crown"`) as from their MOOF images. |
| EveryMan 1, EveryMan 2, Sands of Time | Run, with `--host screen --size 512x342`, from the disk of Jeff Wheeler's games: `--app "EveryMan 1:EveryMan 1"`, `--app "EveryMan 2:EveryMan 2 2.02"` and `--app "Sands of Time:Sands of Time 1.1"` open on a picture beside their author's notes, which say how to start. |
| HyperCard 2.4.1 | Runs, from its System 7 boot disk, with `--app "HyperCard 2.4:HyperCard" --host screen --size 640x480`. It opens the Home stack, and the tabs along its foot go to its other cards. macrt reports that Pack8's selector $0830 and `AESetObjectCallbacks` aren't implemented, and HyperCard goes on without them. |
| Uncle Buddy | Runs, with HyperCard 2.4's boot disk after its own, `unclebuddy.img HyperCardBootSystem7.img --app "READ ME FIRST" --host screen --size 640x480`. OK the stack's alert that Palatino is missing, for the law firm's letter; (more) and Go › Next (Command-3) go on to its next page. |
| Balance of the Planet | Plays, with `--model ii --depth 8 --size 640x480 --host screen`: click its title away, for the results for 1990. Game › Policy Summary lists the taxes and spending; click one for its card, whose scroll bar sets it, and Game › Execute Policies moves the world on five years, to the next results. |
| Oh No! More Lemmings | Plays, in colour, with `--model ii --depth 8 --size 640x480 --app "Oh No! More Lemmings (patched):Oh No! More Lemmings" --host screen`: Lets Go starts the first level, and the lemmings drop from the trapdoor and walk. |
| Particle Man | Plays, with `--model ii --depth 8 --size 640x480 --app "ParticleMan 1.0:ParticleMan 1.0" --host screen`: File › New Game asks which screen to start on, over the high scores. |
| Mac Spudd!, HexOn Exon, Kill Bob, Die, Dobbs, Die!, Haikook | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from the Lamprey Systems disk (`--app "Lamprey Systems Gamesƒ:Mac Spuddƒ:Mac Spudd!"`, and the others in its `Miscƒ` folder). Click Mac Spudd!'s START GAME, then its title, for its story and control panel; two of its menus are titled with a NUL character, which shows as a box. HexOn Exon opens on its encoder, Kill Bob on its target, Die, Dobbs, Die! on its grid and Haikook on its title. |
| Twisted!, Another Fine Mess, A Mess O' Trouble, Ray's Maze, World Builder 1.2 | The games play, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Ray Dunakin's games (`--app " Twisted! ƒ:Twisted! 1.6"`, `--app "Ray's Maze:AMOT:A Mess O' Trouble 1.8"`, `--app "Ray's Maze:AFM:Another Fine Mess 1.8"`, `--app "Ray's Maze:RM:Ray's Maze1.5"`). Each opens on its intro: click the picture or NEXT to go on through it (in A Mess O' Trouble, click A or B to pick a player). Then type a command such as e, n, look, search or inventory and press Return; the scene's picture and text change. World Builder opens to its menus. |
| Devil's Cubes, Ghost, Jotto ][, Kant Generator Pro, Pentominoes | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Mark Pilgrim's games. Each asks for your name the first time. Then File › New game deals Devil's Cubes' puzzle and sets up Ghost's players; Jotto ][ opens on its board, Kant Generator Pro on an editor window and Pentominoes on its Help. |
| 5 Stix, Dr. Macinto, Polytris, PolyMine, Tangram, Poly-Peg | Play, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of S.T. Han's games (`--app "Polytris:Polytris 1.09"` and so on). Demo goes past 5 Stix's and Tangram's registration dialogs to their boards; OK past Polytris's title starts its pieces falling, and past PolyMine's deals its board. Dr. Macinto and Poly-Peg open on their boards. |
| Fist Fighters, M o v o D, Movod II, Quagmire, Sammy the Cyclebot, Color MakeMagic! | Play, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Tony Small's games. OK MOVOD's and Movod II's shareware notices, and a click goes on to Fist Fighters' choice of fighters. Quagmire's File › New Game plays its intro, and Sammy the Cyclebot's starts its first level. Color MakeMagic!'s File › Let's See It! draws a magic square. |
| Edit II, Gamma Zee, Super Sonic the Road Kill | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Dwight Rodgers' programs. Edit II opens a window to type in. Gamma Zee asks whether to play sound and at what speed, then shows its Play and Practice buttons. Road Kill wants a 16-colour screen: with `--depth 4` it plays. |
| Asterbamm, MacSki, TaskMaker, The Tomb of the TaskMaker, Technical Snapshot | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Storm Impact's programs (`--app "MacSki™ v1.7.2:MacSki v1.7.2"`, `--app "TaskMaker v2.2.4:TaskMaker v2.2.4"` and so on). Asterbamm opens on its reminder to register, MacSki, TaskMaker and The Tomb of the TaskMaker on their About windows, with OK, and Technical Snapshot on its licence. |
| Bob vs The Aliens, Cave Dig, Cave Dig 2, Cave Fox, Crystal Rock, Escape Beyond, Mr. Cat's Quest, Star Fighters | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Foxchange's games (`--app "Cave Fox 1.2:Cave Fox 1.2"`, `--app "Cave Dig 2.0.1 :Cave Dig 2"`, with its space, and so on). Bob vs The Aliens and Star Fighters open on their titles, Cave Dig on its Resume, New and Settings, Cave Fox on its choice of foxes and Crystal Rock on its board and its choice of player; Cave Dig 2 and Escape Beyond play their intros. Mr. Cat's Quest 1.4.3 shows its title, 2.5 asks for a register code (Not Yet goes on) and 3.4 opens on "1905, Cat Land". |
| 2nd Terror Protocol, Emergency Blow!, Emergency Blow! v.2, Space Can Suck! | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from the disk of Mobuli's games (`--app "2TP:2nd Terror Protocol"`, `--app "Emergency Blow! v1.0"`, `--app "Emergency Blow!v.2 :Emergency Blow!v.2"` and `--app "Space Can Suck! v.2"`). Each opens on its notes beside a picture; the last three's Quit, Open Game and Begin Game are under them. |
| Bob and Weave, Bob & Weave II, III and 4 | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from the Bob & Weave disk (`--app "Bob and Weave"`, `--app "Bob & Weave II"`, `--app "Bob&Weave3 PPV"` and `--app "Bob & Weave 4 Showtime®"`). The first two open on the ring, with the boxers' scores and gloves' tools, the third on its title, with 1 Player and 2 Players, and the fourth on its arena. Bob & Weave 4 can say a sound isn't defined: Continue goes on. |
| Zoop | Runs, in colour, with `--model ii --depth 8 --size 640x480 --app "Zoop:Zoop™" --host screen`. OK its Preferences, click through its intro, which fades in and out, to its title, and Game › Go starts it: pieces creep in from the four sides toward the square in the middle, where the arrow keys move the shooter. |
| Diamonds, More Diamonds | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app Diamonds`, `--app "More Diamonds"`): Diamonds plays: it opens on its high scores, with Play, Practice, Editor and Quit, and Play starts level 1, where the ball bounces among the bricks, steered with the arrow keys. Their sounds are compressed with MACE, which macrt plays as silence. |
| BBEdit 3.1 | Runs, from the same disk, with `--model ii --depth 8 --size 640x480 --app "BBEdit 3.1:BBEdit 3.1" --host screen`, to a Browser of the disks; its last two menus have icons for titles. Without a desktop database, `PBDTGetPath` isn't implemented. |
| Glider PRO, Glider Edit | Glider PRO plays, in colour, with `--model ii --depth 8 --size 640x480 --app "Glider PRO™ ƒ:Glider PRO™" --host screen`: its title, then the house, Slumberland, with the glider in its first room. Glider Edit (`--app "Utilities ƒ:Glider Edit 1.1.1"`) opens to its File and Edit menus, and File › Open shows its Open dialog. |
| Shattered Stone, Lost and Found, Get Rich Quick, Squirt 3.1 | HyperCard 2.4 stacks, which open with the HyperCard on their disk (`--app "Shattered Stone:Shattered Stone"`, `--app "Get Rich Quick:Get Rich Quick"` and so on), with `--model ii --depth 8 --size 640x480 --host screen`; Lost and Found wants `--memory 6000`. Shattered Stone tells its story, Lost and Found opens on New Game, Load Game and Help, and Get Rich Quick on START and HELP. Squirt 3.1 says the Palatino it wants is missing. |
| FloorTiles 1.1.1, FloorTiles 2.0.2 | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app "FloorTiles 2.0.2:FloorTiles"` and `--app "FloorTiles 1.1.1:FloorTiles"`). FloorTiles 2.0.2 plays: OK its introduction and Not Yet to its request to register, then File › Start New Game and Start, and clicks put coloured tiles on the floor. 1.1.1 shows its shareware notice, then its Match Sides window. |
| Catch the Buzz | Plays, with `--model ii --depth 8 --size 640x480 --app "Catch the Buzz 2.0" --host screen`: Run › Catch The Buzz starts it. |
| Wordtris, Color Wordtris | Play, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app Wordtris`, `--app "Color Wordtris"`): click the title for their setup of game mode, difficulty, level and time limit, then START GAME, and letters drop into the well, steered with the arrow keys. |
| War of Flowers | Plays, with `--model ii --depth 8 --size 640x480 --app "War of Flowers:War of Flowers" --host screen`: give your name, click its title, pick a card to choose who goes first, and the cards are dealt to you and two computer players. |
| Capitalist Pig | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Capitalist Pig®"`, to its copy protection, which asks for a figure from its User Guide. |
| Castle of Ert, Pyramid of Ert | Play, with `--model ii --depth 8 --size 640x480 --host screen`, from the Ert disk (`--app " Castle of Ert"`, with its space, and `--app "Pyramid of Ert V1.2"`). They're World Builder games, played by typing commands: NORTH takes you into the Castle's entrance hall, and in the Pyramid, START, or a click on Start the Game, leaves you in the desert. |
| Glider 2.02, 3.0, 3.1.2 and 3.14, Connect Four | Run on a Mac Plus, with `--model plus --depth 1 --size 512x342`, from The Glider Collection's disk (`--app "Glider 2.02"` and so on) and Connect Four's (`--app "Connect Four"`). |
| Xmas Lemmings | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Xmas Lemmings"`. Clicks go past its intro and its advertisement to the title. LETS GO! shows Level 1, Jingle Lemming, and a click starts it: lemmings drop from the trapdoor and walk, the clock runs, and a skill picked from the panel is given to the lemming clicked. |
| Which Number? 2.0 | Plays, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "WhichNumberIsIncreasing:Which Number? 2.0"`: File › Start New Game starts it. |
| Bachman Game | Its disk's Finder is the game: with `--model ii --depth 8 --size 640x480 --host screen` and `--app "System Folder:Finder"` it opens on its title. |
| Mainframe Hacking CYOA | A HyperCard 2.4 stack, which opens with the HyperCard on the boot disk beside it, given after its own: `MainframeHacker.img HyperCardBootSystem7.img --app "Mainframe Hacking CYOA"`, with `--model ii --depth 8 --size 640x480 --host screen`. It opens on its title card, saying the Palatino it wants is missing. |
| Rocky Shore Discovery | A HyperCard stack, alone on its disk, which opens with the HyperCard 2.4 on another, given after it: `rockyshore.img HyperCardBootSystem7.img --app "Rocky Shore Discovery" --model ii --depth 8 --host screen --size 640x480`. OK HyperCard's alert that Palatino is missing; Start goes to the shore, and a click on an area of it opens that area, with PREDICT and EXPLORE and the stack's buttons along its foot. |
| Fitter Happier | SimpleText opens the poem, with `--app fitterhappier --model ii --depth 8 --host screen --size 640x480`. Its Sound menu, for speaking the text, stays dimmed: the Speech Manager is an extension, which macrt doesn't run. |
| Foobar Versus the DEA | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Foobar Versus the DEA"`: START, then hold a key past the level's story, and the desert scrolls under Foobar's jet, with helicopters to shoot. Its sprites are colour icons (cicn) it plots into an offscreen port. |
| Infinity Quest II, Infinity II Editor | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app "Infinity Quest II:Infinity Quest II 1.0.1"` and `--app "Infinity Quest II:Infinity II Editor 1.0.1"`). Infinity Quest II plays: File › Open a game file opens a quest such as New First Quest, Game › New Game starts it, and the numeric keypad moves Prince Argonn about the level while its monsters roam. |
| Rainbox 1.3 | Runs, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Rainbox 1.3"`, to an empty Untitled1 window, where each click paints a shape in colour; the Toys menu changes it, to a rainbow fan and others. |
| Realms & Reality 1.2 | Plays, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Realms & Reality:Realms & Reality 1.2"`: a World Builder game, played by typing commands; START begins it in your bedroom. |
| 'Round'n'Round | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Round'n'Round:'Round'n'Round (v1.0)"`: past its reminder, Play, and pieces of pipe drop into the pool, steered with the numeric keypad. It wants Sound Manager 3.0, which its disk's System 7.5.3 brings. |
| Secret Agent Joe 1.1 | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Secret Agent Joe 1.1"`: Play Game, then click a point of the compass to go that way, from scene to scene. |
| TAoSR | Plays, with `--model ii --depth 8 --size 640x480 --host screen` and `--app TAoSR`: click its pictures past the BJ COMIX splash and the credits, type START, and the first scene is Your Office. It's a World Builder game, played by typing commands. |
| Super Maze Wars trial | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Super Maze Trial Version 1.0"`: Play, then Ready, and the maze is drawn in 3D; the arrow keys move, and the robots score. Its clock is an extended Time Manager task primed in microseconds. |
| Pyramad, its Guide | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app Pyramad`, `--app Guide`): Pyramad plays: clicks take it past its MagiCastle splash, the temple doors and its title to the board, where blocks are dragged onto the empty squares, matching the sides that touch. The Guide shows a book on a wooden table. |
| Digital Messiah v2.0.1 | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Digital Messiah ƒ:Digital Messiah v.2.0.1"`: clicks go through its intro screens, File › New Game asks your name, Start leaves the story, and the map opens in its window; W, A, D and the other keys of Options › Controls move you about it, and the opponents come for you. Its music plays: from its own disk, with its System, through `SndPlayDoubleBuffer`, and from the 500 Mac Games CD, with BMUG's System 6.0.8, written to the Apple Sound Chip, which it checks Gestalt for and the Mac II has (see [Sound](#sound)). |
| Lenny and Rita, StarGuardian, Mr. Fixitup 3.0.1 | HyperCard 2.2 stacks made into applications, which colour their cards with the AddColor XCMD: with `--model ii --depth 8 --size 640x480 --host screen` (`--app "Lenny and Rita"`, `--app "StarGuardian:StarGuardian"`, `--app "Mr. Fixitup 3.0.1:Mr. Fixitup 3.0.1"`), Lenny and Rita opens on the Lenny Mead Detective Agency's door, StarGuardian on its starry Click on rabbit to continue card, and Mr. Fixitup on its garage, at the screen's top left with the menu bar hidden, as its stack asks (`hide menuBar`). |
| Cairo ShootOut, DataFlow, MS-BASIC | Run, on a Plus (`--model plus`, `--app CairoShootOut`, `--app DataFlow`, `--app MS-BASIC`): Cairo ShootOut to its game screen, DataFlow to its tool palette and windows, and MS-BASIC to its Command and Untitled windows. |
| Mac Attack | Plays, on a Plus (`--model plus --app FINDER`, the name of its program on the disk). At Press mouse button to start, click, then click a level of difficulty, one to three stars, at the top of the screen, and the battle starts: a click fires a shell, which the status panel shows being loaded again, and the enemy's tanks shoot back. |
| Pinball Arcade 1.1 | Plays, on a Plus (`--model plus --app "Pinball Arcade"`): click past its title, open a table from the pinball games folder in the Standard File dialog it puts up, and pick File > Play Game and the number of players. With `--model ii --depth 8 --size 640x480 --host screen` it runs as well, but draws its ball straight into the screen's memory a bit to a pixel, as on a black-and-white Mac, which at 8 bits a pixel shows as specks of colour. |
| Fortune 0.5 | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Mac Fortune:Fortune 0.5"`, to a fortune in its window; the right and left arrow keys go to the next fortune and back, the window fitting each one, and Fortune › Prefs… sets where the window goes and when the next fortune comes. It starts the Communications Toolbox's managers, which macrt doesn't have, and goes on without them. |
| MYSTy 2.0 | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "MYSTy 2.0(68k)ƒ:MYSTy 2.0(68k)"`, to its question of how many colours the Mac shows. Answer 256, and it goes on to Shareware Version 2.0 and Click to begin; a click shows the TWIN Software logo. The next click stops it with HyperCard's alert of No such window: the stack's scripts play its QuickTime movies through the Movie XCMD, which opens a window for each, and macrt has no QuickTime. |
| System's Twilight | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "System's Twilight"`. New Game asks where to save the game, then tells The Beginning. The right-hand arrow at the top left of the panel goes on through the story, the left-hand one back, to Mazer's Tale, where a click walks Mazer and he talks in balloons. |
| Grey Tower, Palace of Sand, Canal District, Color by Number, Muddy Water, Color Pavilion, The Sultan's Palace, Double Trouble | Graphic adventures from one disk: run, with `--model ii --depth 8 --size 640x480 --host screen`, to their first scenes, most of them in colour (`--app "Grey Tower 1.5.2 ƒ:Grey Tower"`, `--app "Palace of Sand 1.6.1:Palace of Sand"`, `--app "Canal ƒ:Canal District"`, `--app "ColorByNumber 1.2.2 ƒ:Color by Number"`, `--app "Muddy Water 1.3.2 ƒ:Muddy Water"`, `--app "Pavilion 1.4.2 ƒ:Color Pavilion"`, `--app "Sultan ƒ:The Sultan's Palace"`, `--app "Double ƒ:Double Trouble"`). |
| Morse Mania, MorseTrainer US-1.1 | Run, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app "MorseMania(1.0):Morse Mania"`, `--app "MorseTrainer US-1.1:MorseTrainer US-1.1"`): Morse Mania to its hints, and MorseTrainer to its trainer window, with its Train pop-up menu. |
| MacGlobe 1.5.0 | Runs, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "MacGlobe:MacGlobe"`. OK the AutoDoubler notice, click past its title, and its map of the world names the country or sea under the pointer; with Paint, a colour from its bar colours the country clicked. |
| BiPlane 2.0 | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "BiPlane™ Shareware"`: OK its about box for an empty spreadsheet. Click a cell and type, and Return enters the value and moves down; a formula such as `=A1+A2` shows its sum. |
| Magic Castle | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Magic Castle"`: its Main Menu, and Exploring the Castle. |
| StoryMaker 1.0, and games made with it: The Great LightBulb Adventure 1.3, Louis Street Adventure, Adventure Island, Country House 1.0, Jailbreak | StoryMaker runs and the games play, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk (`--app "StoryMaker 1.0:StoryMaker 1.0"`, `--app "LightBulb Adventure 1.3 folder:The Great LightBulb Adventure"`, `--app "Louis Street Adventure:Louis Street Adventure"`, `--app "Adventure Island:Adventure Island"`, `--app "Country House 1.0:Country House 1.0"`, `--app "Jailbreak:Jailbreak"`). Not Yet in StoryMaker's registration dialog brings up an Open dialog: open Sample Game, and its rooms, items and map open in their editors. In the games, type a command such as look or n and press Return, or click in the room's picture. |
| The Journey 1.6.2 | Plays, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "The Journey 1.6.2 US"`. START shows the crashing spaceship and its text window. Commands come from the Commands menu (North … Close, Look, Inventory) or are typed, with Return, and the parser answers. Going South without the report ends the game. |
| Heaven & Earth | Plays, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Heaven & Earth:Heaven & Earth"`: Continue in its Welcome Traveler! dialog, then click one of the gateway's objects, the left one for the Pendulum. This disk has its black-and-white pictures only. |
| Maniac 2.1 | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Maniac 2.1 ƒ:Maniac 2.1"`: type N at the main menu for a new game, a maze game like Pac-Man. |
| The Venice Project | Plays, on a Plus (`--model plus --app "The Venice Project™"`): type the word its opening text asks for in the box and click Okay, then OKAY on the title, and it dials in to its system and asks for a password. |
| Rodney's Funscreen | Runs, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Rodney's Funscreen:Rodney's Funscreen"`, to its copy protection, which asks for its monster's name from the Funscreen guide. |
| Treasure MathStorm! 1.0 | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Treasure MathStorm 1.0"`: click through its title and story to its Club Sign-In, then Start Game, and Chirp the snowbird's hints lead into the first cave. Its story's font is only bold in its FOND, its styled text has a lineHeight and no fontAscent, and its port's rectProc draws nothing, so that TextEdit's erasing leaves the panels' colour behind the text. |
| Museum Madness | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Museum Madness:Museum"`. Click past its title, and the boy tells his story in his bedroom; Escape skips it, to the museum's lobby. There the pointer turns into a hand over what can be clicked: hold the button a moment, as the game reads it with Button between frames rather than waiting for a click, and the boy walks there; on the robot, the two of them talk. It moves the mouse itself, through the cursor's task in the low-memory vector JCrsrTask. |
| Widget Workshop 1.4 | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Widget Workshop 1.4:Widget Workshop™"`. Click past the title into the workshop. Puzzles lists the puzzles in its Puzzles file, and OK opens one in the editor: its parts can be picked, and GO runs the widget. It counts the puzzles with CountResources while its own file is current, which takes in every open resource file. |
| Bulldozer, Voracity, Robottack, Olive Wars!, Tennis, Hockey | Play, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from a disk of games (`--app "Program Files:Bulldozer"` and so on). Bulldozer's arrow keys drive it, pushing the boulders; Voracity's arrow and keypad keys move it, eating digits for its score; in Robottack the keypad's numbers move you among the robots that chase you. Olive Wars!, Tennis and Hockey start with ⌘N. In Olive Wars! the left and right arrow keys move the olive; it draws its frames only when WaitNextEvent returns an event, and passes an empty mouse region, so it's the mouse-moved events it's given that keep it going, and its sprites are drawn in the arithmetic transfer modes. In Tennis and Hockey, S, X, Z and C move the first player up, down, left and right. |
| Ultimine | Runs, in colour, the same way, to its game window. It sets its window's portRect itself while the window's hidden, to measure the frame around it, and its window's regions are worked out again from that when it's shown. |
| Evolve, Lasso, MazeRace, Space Combat, StackBlitz, Head-On Collision, Laser Clash, Cheesy Pursuit, Bulldozer II, Core Meltdown, Hex, Moku, Reversi Plus, Tic Tac Toe 3D | Play, in colour, the same way, from the same disk (`--app "Program Files:Hex"` and so on). Evolve, Lasso, MazeRace, Space Combat and StackBlitz start with ⌘N, and Head-On Collision when an arrow key first steers your car. The arrow keys move Cheesy Pursuit's mouse among the cats, eating the cheese; Laser Clash's light trail, against three robot players; Bulldozer II's bulldozer; and StackBlitz's falling pieces. In Core Meltdown, Hex, Moku, Reversi Plus and Tic Tac Toe 3D you click where to play, and the computer answers. |
| Black Box Chess, Brain Bones, Bulldozer Builder, CardMatch, Checker Connector, Cryptograms, Engulf, Hexapawn, Neutron Trails, Nim, Pegopolis, Poker Machine, Poker Patience, Push-Pull, Quinto, Sechseck, Siege, Think Tank, Vanishing Cross, Wari, Winding Standoff, Expert Games Browser | Run, in colour, the same way, from the same disk, to their game windows. Poker Machine opens on its casino's sign-in. Bulldozer Builder's window is taller than a 640×480 screen. The browser lists the games, with a picture and a description of each. When its window is activated it takes the refCon of each control in it that's above 10 to be one of its own records, and the scroll bar of its list holds the list's handle there, so whether it carries on depends on what's in the heap past the list's master pointer; here it does, with the application heap's master pointers made 64 at a time, as Inside Macintosh II documents. |
| Megapode stack | A HyperCard stack, which opens with the HyperCard 2.4 on the disk that comes with it, given after it: `DouglasAdamsMegapode.img HyperCardSys7.img --app "megapode stack" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing, for its card that works out the volume of a megapode's nest from the sizes typed into it. |
| The Hitchhiker's Guide to the Galaxy (Voyager Expanded Book) | A HyperCard stack, which opens with HyperCard 2.4's boot disk after its own: `H2G2.img HyperCardBootSystem7.img --app "Hitchhiker's Guide" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing and click past the title twice: it asks for a name to register the copy with, then opens its Expanded Books Help Topics. |
| The BeerStack 1.1, The BeerStack 1.1 Info | The stack opens with HyperCard 2.4's boot disk after its own: `TheBeerStack.img HyperCardBootSystem7.img --app "The BeerStack 1.1" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing, for its board of topics; a click on one, such as Beer?, opens its information window. The Info beside it is an application of its own (`--app "The BeerStack 1.1 Info"`), which opens on Welcome to The BeerStack. |
| Stranger Things | A HyperCard stack, whose disk comes with a HyperCard boot volume. The HyperCard Player at that volume's top level asks Where is Home?, so name the HyperCard 2.4 in its folder before the stack: `StrangerThings.img HypercardBootVolume.img --app "HyperCard 2.4:HyperCard" --app "Stranger Things" --model ii --depth 8 --size 640x480 --host screen` (see [Opening a document](#opening-a-document)). OK the alert that Palatino is missing, and its slides play, from the STRANGER THINGS title on. |
| Clinton Issues Stack | Runs with the HyperCard 2.0 on its disk, `--app "Clinton Issues Stack" --model ii --depth 1 --size 640x480 --host screen`, and opens on a field of stars, then a portrait. At `--depth 8` HyperCard says it needs more memory to run at that colour setting. |
| MacJesus | A HyperCard stack, which runs with the HyperCard 1.2.5 on its disk given more memory than the 1000K it asks for: `--app MacJesus --memory 3000 --model ii --depth 8 --size 640x480 --host screen`. Its card has Start MacJesus and its other buttons, and the face changes from one moment to the next. With 1500K, HyperCard says it doesn't have enough memory to continue. |
| Dick & Jane (William Dickey's Hyperpoems, volume 1) | A HyperCard stack, which opens with HyperCard 2.4's boot disk after its own: `volume1.img HyperCardBootSystem7.img --app "Dick & Jane" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing, for its title, Dick & Jane & Spot & the Inspector-General; the poet's portrait at its foot goes on to the poem, The scene: an English country house. |
| Monopoly (MacPlay, B&W) | Plays, on a Plus, with `--app "MONOPOLY™ (B&W)" --host screen --size 512x342`: click past its title, and Game › New… asks for the first player. On a colour screen it says it wants the screen set to black and white. |
| Beyond Cyberpunk! | A HyperCard stack, the CyberDeck, which wants more memory than HyperCard 2.4 asks for, and HyperCard 2.4's boot disk: `HyperCardBootSystem7.img BeyondCyberpunk.img --app "HyperCard 2.4:HyperCard" --app "0 CyberDeck (v.1.5)" --memory 6000 --model ii --depth 8 --size 640x480 --host screen`. Its MacroMind Director title plays, then Brought to you by.... The Computer Lab; JACK IN goes on to Jacked In!!!. With HyperCard's own size it stops with Out of memory, and the HyperCard on its own disk asks Where is Home?, as there's no Home stack beside it. |
| The Secret of Monkey Island | Plays, in colour: `MonkeyIsland.img --app "Monkey Island" --model ii --depth 8 --size 640x480 --host screen`. Escape skips the opening, and again the scene at the lookout, for the dock, with the verbs (Give, Pick up, Use…) below it; a click in the scene walks Guybrush there. |
| Netscape Navigator 2.02 | Browses the web pages on its disk: `Octavian.img --app "Netscape Navigator™ 2.02" --model ii --depth 8 --size 640x480 --host screen`. Accept the licence, and OK the alert that it couldn't make a network connection, as there's no network. File › Open Location… then takes a `file:` URL, such as `file:///Octavian/Octavian/start.html`: the pages come with their pictures, tiled backgrounds and styled text, links go from one to the next, and Back and the scroll bar work. |
| MacPaint® Demo | Paints, from the Letterforms & Illusion disk: `landi.img --app "MacPaint® Demo" --model ii --depth 8 --size 640x480 --host screen`. It opens Untitled-1, and its Tools and Patterns menus draw palettes of their own, which tear off; a drag in the window draws. |
| Adventures of Sean 2 | A HyperCard stack, which plays with HyperCard 2.4's boot disk after its own: `AdventuresOfSean.img HyperCardBootSystem7.img --app "Adventures of Sean 2" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing; File › Begin new game starts in a dark room, which lights up when you find its light switch and click it. Sean › Inventory shows what Sean carries. |
| Your Apple Tour of the Macintosh SE | Plays, on the default Plus: `--app "Tour Engine" --host screen --size 512x342`. Apple's tour opens on a city street, "Right now, thousands of people are using the Apple Macintosh computer to get things done", and goes on to pointing, clicking and dragging. |
| The Religion of Islam | An application made from a HyperCard stack, which runs on its own: `ReligionOfIslam.img --app "The Religion of Islam" --model ii --depth 8 --size 640x480 --host screen`. Its Islam: Introduction window opens on its publisher's title, in colour, then its authors. |
| Twin Peaks BS Companion | A HyperCard stack, which opens with HyperCard 2.4's boot disk after its own: `Twin_Peaks_BS_Companion_V2.img HyperCardBootSystem7.img --app "Twin Peaks BS Companion" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing, for its title card, The Twin Peaks Bedside Companion; its buttons go on to its sections, People to a chart of Laura Palmer's friends and family. |
| The List of RRHost BBSs | A HyperCard stack, which opens the same way: `RRHost_BBS_List_1987.img HyperCardBootSystem7.img --app "The List of RRHost BBSs" --model ii --depth 8 --size 640x480 --host screen`. Its title card's arrow goes on through the bulletin boards running Red Ryder Host in September 1987, a card for each, with its number, its sysop, its hours and its speeds. |
| Clue | A HyperCard stack, in colour. The HyperCard on its disk asks Where is Home?, so name the HyperCard 2.4 on its boot disk first: `HyperCardBootSystem7.img clueandcluedeluxe.img --app "HyperCard 2.4:HyperCard" --app "Clue" --model ii --depth 8 --size 640x480 --host screen`. What's the Story? tells the story of Mr. Body, and Go to Game Board, then NEW, sets out the board and the Detective Notes. |
| Evocation: la Sfida | Plays, in colour: `Evocation.img --app EvocatioN --model ii --depth 8 --size 640x480 --host screen`. Click the EVOCATION FINAL badge on the title to start. The eyes, hand, orb, mouth and cap above the scene pick what to do, and the name of what the pointer is over shows in the box below it. Its ? turns on balloon help, which macrt doesn't show. |
| Infidel, Suspect, Cutthroats | Play, on the default Plus, from their raw images (`00playable.dc42`, `--app Infidel` and so on): type a command such as `inventory` at the prompt, then Return. |
| MacCopy | Runs, on the default Plus, from its raw image (`--app MacCopy`), to its window with the internal and external drives and Duplicate, Format, Verify and Eject buttons for each. |
| MacBackup 2.6 | Runs, on the default Plus, from its raw image (`--app MacBackup`), to its title and its notice about copying software; Continue goes on to ask for the original disk in the internal drive and a blank one in the external. |
| Brock Keystroke | Runs, on the default Plus, from its raw image (`--app "BROCK KEYSTROKE"`), and opens New Form, which takes what's typed. |
| SuperPaint 2.0 | Paints, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "SuperPaint 2.0"`: it opens Untitled - 1 between its tool and pattern palettes, a click on a tool picks it, and a drag in the window draws with it. Its palettes are windows it keeps in front, and it activates the document window behind them itself, storing it in the Window Manager's CurActivate for the Event Manager to report. |
| Dvorak On Typing | Runs, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Dvorak On Typing"`: it asks who you are, and a new name typed, then Return, goes on to its Main Menu of Lessons, Reports, Game, Custom and Preferences. |
| 1987 HyperCard Supplement, DM 3000 | HyperCard stacks, which open with HyperCard 2.4's boot disk after their own: `annual_report.img HyperCardBootSystem7.img --app "1987 HyperCard Supplement" --model ii --depth 8 --size 640x480 --host screen`. Apple's supplement to its 1987 annual report opens on Welcome to the HyperCard Supplement, and a click goes on. DM 3000, from the disk beside it (`disk.img`, `--app "DM 3000"`), opens on Death Mall 3000's title and story, with RECAP, QUIT and MOVE ON. |
| froyofonts compact | Runs on its own, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "froyofonts compact"`, and shows its typefaces a card at a time; the arrow goes on to the next. |
| Teach Yourself HyperCard | The HyperCard 1.2.5 on its disk opens its Home card: `TeachYourselfHyperCard.img HyperCardBootSystem7.img --app HyperCard --model ii --depth 8 --size 640x480 --host screen`, whose arrows go on to its other cards. The disk's lesson stacks open by name in the same way (`--app "FINAL Pracstack"`, `Reference`, `sample`, `"CIRCUS CLOWNS"`). Intro and the Home card's other stacks aren't on the disk, so a click on one asks where it is. |
| The Bee, Ziggy Gets Out, Phonics Workout, Symbols, Word Parts | Anne and Richard Wanderman's stacks, which run on their own from their disk with `--model ii --depth 8 --size 640x480 --host screen` (`--app "The Bee v. 1.2"`, `--app "Ziggy Gets Out"`, `--app "Phonics Workout"`, `--app Symbols`, `--app "Word Parts"`). Ziggy Gets Out's arrows turn the story's pages, and Phonics Workout's go from one word to the next. |
| TesselMania!, Start TesselMania! | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from their disk: TesselMania! (`--app "TesselMania!®"`) opens on its moving title, with Instructions…, Open… and New…, and Start TesselMania! (`--app "Start TesselMania!®"`) shows MECC's TesselMania! Deluxe Preview. |
| Spaceship Warlock | Plays its opening, in colour: `SSWarlock.img --app "Spaceship Warlock™" --model ii --depth 8 --size 640x480 --host screen`. Reactor's logo, then the story's text, with arrows back and on. It reads the screen's modes from its card's declaration ROM with the Slot Manager. |
| How God Makes God | A MacroMind Director movie: `HGMG.img --app " • How God Makes God" --model ii --depth 8 --size 640x480 --host screen`. It asks for its CAMELOT font to be installed in the System file, and OK goes on to its menu of Index, Beginning, About and Quit. |
| TidBITS 1–50, TidBITS 51–100, TidBITS 101–150 | The newsletter's first issues, as HyperCard stacks that open with HyperCard 2.4's boot disk after their own: `TidBITS.img HyperCardBootSystem7.img --app TidBITS1to50 --model ii --depth 8 --size 640x480 --host screen`, and `--app TidBITS51to100`. Issues 101 to 147 are Easy View files: `TidBITS101147.img --app "TidBITS 101-150"` opens Easy View on their index. |
| The Ambrosia Times 1.2 | Ambrosia Software's newsletter, a DOCMaker document: `TheAmbrosiaTimesVol1Iss2.img --app "The Ambrosia Times 1.2 " --model ii --depth 8 --size 640x480 --host screen` (the name ends in a space). |
| Marathon Demo | Plays, in colour, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Marathon Demo"`: its main menu's Begin New Game starts a game. |
| Wallpaper 2.0 | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Wallpaper 2.0"`: it asks to switch the screen to black and white, then shows its pattern generator. |
| Mario's Game Gallery, Mario's FUNdamentals 1.1 | Run, in colour, with `--model ii --depth 8 --size 640x480 --host screen`, from their disks (`--app "Mario's Game Gallery"`, `--app "Mario's FUNdamentals 1.1"`), to their menus of games; Checkers opens its board. |
| Mac Format's cover floppies | `MacFormat35Floppy.img`, the magazine's cover disks in folders such as `MacFormat 9`, has no System of its own: run it with `--system MacDemoGames.img` (the CD above) and `--model ii --depth 8 --size 640x480 --host screen`, naming each program by its path, as `--app "MacFormat 9:SimCity 2000 Demo Folder:SimCity2000™ Interactive Demo"`. Of the 55 games and demos tried, all start and none stops with an error: among them Wolfenstein 3D, Lemmings and Oh No! More Lemmings, Shatterball, Firefall, GNU Chess, Syndicate, Spectre Supreme, Maniac, Mombasa, Glypha III, Oxyd, Civilization, Operation Intercept and Maelstrom. Prince of Persia 2 plays. Populous II draws its title as its window's own picture (`SetWindowPic`) and goes on to its map. SimCity 2000's demo cycles its colours during its splash before it has made the colour tables it cycles, and goes on to its city. Tetris 2000 and Star 'Roids play from their Game menus, and Pathways into Darkness, given a name for a new game from File › New, opens its view of the pyramid and its welcome. Patriot Command says it runs only on A/UX, as it does on the Mac OS. Among its utilities, GraphicConverter 2.0.6 (`--app "MacFormat 24:GraphicConverter 2.0.6:GraphicConverter"`) opens the pictures on the disk, such as the model in `MacFormat 15:GrayStation 1`, beside its tools and its picture's information, once its About box is OK'd; SoundApp (`MacFormat 34:SoundApp:SoundApp`) plays a sound chosen from File › Open, such as the HyperStudio Preview's Parrot; DOCMaker 4.1 asks for a document to open; and FlashWorks opens on its flash cards. HomePublisher's demo (`MacFormat 16:HomePublisher Demo:HomePublisher™ DEMO`, its code loaded into a System 7 heap with room to grow) opens its New/Open Publication dialog, and Factory (`MacFormat 31:Factory:Factory 1.1`) plays from Game › Begin, given a name and no check number for a new game. Starter Accounts (`MacFormat 4:Ritz Starter Accounts ƒ:Starter Accounts`), a compiled BASIC program, opens on its main screen, asking for a data file from its File menu: its runtime sizes its workspace from `FreeMem` and `MaxMem` and grows its locked program handle into it. TechTool (`MacFormat 18:Troubleshooting:TechTool™ 1.0.4 ƒ:TechTool™`) shows its introduction and then its menus, which hold its work (File › Rebuild Desktop and Zap PRAM); its information window, which its Open Application handler opens, doesn't appear, because the introduction's `ModalDialog` gets that event first and its filter returns FALSE for it, and for an event the filter doesn't handle "ModalDialog does nothing" (*Inside Macintosh: Macintosh Toolbox Essentials*, Dialog Manager, ModalDialog). Fast Player asks Gestalt for QuickTime, which macrt doesn't have, and quits. Addresses & Birthdays stops with an error: its start-up code copies its globals from two bytes past the end of its `DATA` resource. |
| Gary's HyperCard stacks | `GarysHyperCardPage.img`, with a HyperCard Player and stacks such as Car Care, The Cruel Fairy, Frappie the Frog, the Honey Do List, HyperEnvelope, Storybook, Tubers, HyperPatterns, Triangles and a SETI@home calculator, has no System of its own: run it with `--system MacDemoGames.img` and `--model ii --depth 8 --size 640x480 --host screen`, naming the stack by its path, as `--app "GarysHyperCardPage:CarCare Folder:Car Care"`. The Player says Palatino is missing, as neither disk has it; OK that, and each opens on its first card. Where a stack's card is bigger than the card window, the Player shows its Scroll window itself. |
| Thoru Yamamoto's stacks | The stacks A Little Tree, Drug Store, Hand To Hand and HandToHand-X, See The Sky and the zizi series, on a disk named Thoru Yamamoto with no HyperCard of its own: give HyperCard 2.4's boot disk after it, `disk.img HyperCardBootSystem7.img --app "Thoru Yamamoto:A Little Tree" --model ii --depth 8 --size 640x480 --host screen`. OK the alert that Palatino is missing, and each plays its opening: HandToHand-X's hiragana around Click a Word!, zizi's title, Drug Store's moon. |
| Deco | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app Deco`: past its notice, it shows its board. |
| M&M's Shockwave games | From `MMS1996.img`, with `--model ii --depth 8 --size 640x480 --host screen`: `--app bagem` plays, `--app melt` shows Melt 'em's pool, and `--app paintem.sea.1` Paint 'em's palette and canvas. |
| LEGO DACTA Control Lab 1.0 | Runs, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "CtrLab 1.0"`. It looks for its interface box on the modem port and says it can't find it; OK goes on to its Command Center, and File › New Project opens Untitled (Setup), with the box's inputs 1 to 8 and outputs A to H and the sensors and motors to connect to them. |
| Macromedia Flash 2 | Starts, with `--model ii --depth 8 --size 640x480 --host screen` and `--app "Flash 2"` (`MacromediaFlash2.img`): its splash, then its tool palette and its Quick Start lesson behind the Macromedia Flash Serialization dialog, whose name, organization and serial number fields take what's typed. There's no serial number on the disk, and Cancel quits. It makes its own table of the keys from the `KCHR` that GetScriptManagerVariable(smKCHRCache) points to. |
| A CD of game demos | `MacDemoGames.img`, with System 7.5.5 and fifty demos in its More Information folder, each named by its path, as `--app "More Information:Tristan™:TRISTAN™ DEMO"`, with `--model ii --depth 8 --size 640x480 --host screen`. Nearly all reach their titles or play: Prince of Persia's palace, Battle Chess's board, Color Super Tetris, Crystal Quest, Lemmings, Glider 4.06, Spectre, Xanthus, SimAnt and Warlords past their notices, and Tesserae's mosaic. Mission Starlight turns its sound on by setting a bit of the VIA's with `BitSet`, and goes on to its game screen. Tristan opens its External Sound file again for each game and looks for its sounds there, and plays. Pararena asks for 16 or 2 colours and, given 16, sets the screen to them itself and shows its title. OIDS, RoboSport, Color VETTE! and Armor Alley want 2 or 16 colours, and run with `--depth 4`; Armor Alley also runs at 256 colours with `--memory 5000`. Mission Thunderbolt needs `--memory 6000`, and without it says its memory is critically low. Checkmate is a black-and-white demo and says so. The Journeyman Project's Sneak Preview and The Iron Helix's demo play their music from AIFF files with play from disk: Journeyman goes on past its burned city into the time machine, and Iron Helix shows its walkthrough on the ship's console, then its title, and quits when it is over, as it should. Rommel and Panzer Battles want 16 colours, or 2 for their black-and-white scenarios, and run with `--depth 4` or `--depth 1`; each asks for a scenario in an Open dialog and goes on to its Game Preparation dialog. Rodney's Funscreen shows its tent, and a click on a game, such as Guess-O-Matic, starts it. |
| BMUG's PD-ROM Volume 1 | `BMUGPDROMVolume1.img`, a CD of public-domain and shareware programs with its own System Folder (System 6.0.8), runs on the default Plus, naming each program by its path, as `--app "PD ROM:Games:Arcade:AirTrafficController 4.0"`. All 174 programs in its Games folder start: among them Air Traffic Controller 4.0, whose author's address is a button with a title of three lines, Star Fleet Battles Playing Aid, MacYahtzee, Mouse Craps, Canfield, Royal Trick-Track and Euchre. The Fool's Errand's demo asks for its Demo Puzzles file in an Open dialog and goes on to the first page of its story, The Sun. Crozzle 0.8 calls `NewWindow` as `$AB13`, with bit 9 of the trap word set, which a Plus ignores. Vampire Castle speaks with MacinTalk, which the CD doesn't have, and without it stops with an illegal instruction the first time it speaks. Juggler reads its own file from the top of the disk rather than from its folder, and says error -43; so do Aquarium and Fido, in its Graphics folder, and Camera, in Education, which open their data forks by the volume of the file control block of their resource file, and a volume reference number with a name and no directory names the file in the volume's top directory. Copied out of the image with their resource forks, into a folder of their own on the computer, they find their files: Aquarium shows its fish and its snail, Fido its dog, and Camera its camera and a slide. Silicon Volleyball 2.0 looks for itself under its old name, Silicon Volleyball, and says it can't find its Hall of Fame. Beyond its games, HyperCard 1.2.1 opens the CD's home stack; LaserKey's installer makes its own item list, its text all user items whose procedures it puts there itself; TME's first menu is a space and an apple; and JamPaint, a paint program for AppleTalk networks, finds the printer port configured for the Serial Driver and says error -98 without trying to open AppleTalk. Among its utilities, Cipher 1.00 is a program for PShell, the Pascal interpreter beside it: it names itself in its Finder information and launches PShell, which shows Cipher's title and asks for the cipher to solve. Mount any Hard Disk looks for drives on the SCSI bus and, finding none (the disks macrt mounts aren't on a bus), quits. SCSI Evaluator 1.00 has `NumToString` put each of its numbers at NIL, address 0, and draws them from there. CassetteLabeler 1.0b1 stops with a bus error: its BASIC runtime goes on using a window it has disposed of. All but three of its other utilities and its virus tools start, from Icon Extractor, ICONstructor, SicnEdit and Zoomation to MacSnoop, Sample It!, RamDisk+, Ferret, Interferon and Virus Rx; SnapShot's installer zooms frames in the screen port where each of its windows is about to come, before it shows the window over them. ResEdit 1.2d2 stops with an illegal instruction at $2A: after its first `ParamText` it goes through the volume queue and calls through the long at $700, an address Inside Macintosh doesn't document, which macrt leaves 0; Memdoggie stops at `_OSDispatch` selector $17, which isn't documented either; and REMOVE*JCLOCK passes `InitGraf` 0 rather than the address of its `thePort`, so `InitGraf` stops with a bus error setting up the QuickDraw globals below it. In its Mac II folder, MPWAccuracy, which tests the accuracy of floating-point arithmetic, runs to the end of its table of results with `--model ii --depth 8`; macrt runs the 68020 and 68881 instructions it uses that the processor core doesn't (`CHK2`, packed decimal `FMOVE`, `FSAVE` and `FRESTORE`) itself. Mandelbrot 2.7 draws its picture with `--model ii --depth 8 --row-bytes 1024`: it writes each row of its 450-pixel map into the screen's memory 1024 bytes after the last, rather than as many as `screenBits` says. Color IconBounce, from its Graphics folder, bounces colour icons over the screen with the same `--row-bytes 1024` (and with `--depth 4 --row-bytes 512`); it copies its picture of the screen into the screen's memory itself, its rows 128 bytes apart for each bit of a pixel. JuliaSet 5.1 draws its Julia set with `--model ii --depth 8`: it reads the screen's mode from the System file's 'scrn' resource, where the Control Panel records how the screen is set up, and macrt's System file has one for the screen as it starts. Mandel881 and MandelSANE, in Updates/New, draw the Mandelbrot set with `--model ii --depth 8 --memory 4096`. They have no `SIZE` resource, so macrt gives them 1 MB, and each asks `NewPtr` for 2400K, 8 bytes for each pixel of a 640×480 screen; without the memory, they say they won't be able to refresh their window. Rainbow draws its string art in colour with `--model ii --depth 8`, writing the pixel value of each colour into its port's `fgColor` itself; Spectra draws whichever of its shapes is picked from its Shapes menu; and Flock's points flock in the window File › Flock opens. QuickBenchMark stops with a divide by zero when one of its tests takes less than a tick, as its test of the blend mode does in macrt. MonsterPaint, in Graphics, runs with `--model ii --depth 8 --memory 4096`: it has no `SIZE` resource, and its four 576×720 pixel maps don't fit in 1 MB. Its pencil starts in white, the first colour of the standard table; to draw in another, hold the button down on a colour in its palette, as it reads the colour only while the button is down. ColorArt, with `--model ii --depth 8`, draws coloured lines and shapes once Go › Start is picked, all in the top left 512×342 of the screen, as its own arithmetic places them there. Colorize v2 asks in an Open dialog for the program whose colours to change and lists the parts of its windows, dialogs, controls and menu bar; clicking one brings up the Color Picker, which in macrt is the host's colour dialog with Colorize's prompt as its title, and OK writes the colours into the program's resources and asks for the next. MandelZot 0.5's File › New draws the Mandelbrot set a point at a time, in whichever of the modes in its Display menu is picked. Mesmer's File › Start draws string art in colours it cycles, Spirograph Mac II draws its patterns from the start, and StarMapper Mac II draws its star map once the four values its form asks for are typed. Discovery Color Images plays a sound and then shows its photographs one after another; Display, in Graphics:Balls, asks for its Balls file and shows a ray-traced picture of four balls; and Show Screens, with `--row-bytes 1024`, shows the screens saved beside it, cycling their colours, as it unpacks each row into the screen's memory 1024 bytes after the last. Lichtenstein fills the screen with circles, boxes and lines in random colours. Wallpaper and FKey Manager say they need the screen in two colours, and with `--depth 1` they run. BackPrint v1.3 copies its INIT and driver into the System file and quits. With `--model ii --depth 8 --size 640x480` its Games and Graphics run as they do on the Plus, but for a few. Hustle and Think Ahead+ 1.3 need a 68000: the `TRAP` handlers of their Forth runtime expect the 68000's six-byte exception frame, and with the 68020's, which adds a format and vector offset word, they stop with a bus error in `SetCursor`. With `--model ii` macrt's Toolbox trap table has 1024 entries, so Crozzle's `$AB13` is trap $313, which isn't implemented, and Crozzle stops there. RingWarp keeps the size of the screen it fills in a word that a 640×480 screen overflows; it runs with `--size 512x342 --depth 1`. PackIt III, taking the Mac II's `ROM85` for an older ROM's, grows its heap itself, as programs for the 64K ROM did. MirrorBalls and Wide Flight write into the screen's memory a bit a pixel, and LAZlife sizes its window by the screen's rowBytes; they run with `--depth 1`. Vanlandingham wants a 512×342 screen, and on a bigger one says it hasn't enough memory. Notebook 2.0's `SIZE` resource asks for 253K, and with a 640×480 screen it says memory is low; with `--memory 512` it opens its notebook. Digital Clock, in Business, writes into the screen's memory a bit a pixel, and runs with `--depth 1`. AutoBlack, a screen saver, says on a Mac II that it can't find the screen hardware. PadDesign puts its second window at (450, 400) on the screen, past the bottom right of a 512×342 one, and on a 640×480 screen its corner shows there; GLA 1.5 places its window by the size of the screen, at its bottom right; and Synchronicity, in Pictures, makes its window 512×322 whatever the screen's size. On a Mac II, FontFkeyDAPntgSound Sampler, in FKEYs, puts its six menus in the list of submenus, `InsertMenu` with -1, and adds a menu, Hi!, to reach them; but the item strings it gives `AppendMenu` have the character $1B and each menu's ID as part of the text, without the `/` and `!` that make them the command and mark of an item with a submenu, so its items show those characters and have no submenus. On a Plus it puts its menus in the menu bar. Idealiner Jr 2.2, in Text, starts with an Open dialog of its own whose New button, item 2, starts a new outline. ICN#->ICON, in Stacks, has a `wctb` 0 of its own, and on a Mac II its window's frame is in its colours: a blue outline and stripes, a cyan title bar and a red title. |
| BMUG's PD-ROM Volume 2 | `BMUGPDROM2.img`, the second CD, has no System Folder, so give it Volume 1's with `--system BMUGPDROMVolume1.img` and name each program by its path, as `--app "Games:Strategy:CrossWise"`, on the default Plus. Nearly all the programs tried so far start. Burtonia, a THINK C console program, installs its own driver with DrvrInstall. The Arkanoid Demo and Yeager's AFT draw in the alternate screen, and MyTimeDemo reads the dates typed into it with StringToDate. Crab Attack II needs `--memory 800`: its SIZE asks for 500K, and it takes seven 51,840-byte buffers with NewPtr. CrossWise needs `--memory 320`: its SIZE asks for 270K, and it won't go on unless MaxMem gives it 256,000 bytes. PSpice Tour Engine runs with `--model ii --memory 1500`. On a Plus, after checking ROM85, it reads addresses past the end of RAM and stops with a bus error. Ballistics v2 waits for a click before it plays. Fortune shows a saying and quits a few seconds later. Tic-Tac-Toe-Too paints the screen black and asks for a board size in its console. Core War's programs smear as they crawl, which comes from the way it copies them. MacNPCGenerator reports 96 MB free, as every macrt volume does. Vampire Castle and The Birds want MacinTalk, which macrt doesn't provide. World Class Demo looks for a file called World Class, which isn't on the CD, and says File Not Found. Juggler, Silicon Volleyball 2.0 and Aquarium behave as their copies on Volume 1 do. Bomber draws a pretend system error, with its own copy of the Finder's menus. Crystal Paint DEMO sets the LoadTrap byte, so each segment it loads is handed to `_Debugger` first, and installs its own A-line trap handler, which chains to the one it replaced. Icon Exchanger hands PlotIcon handles whose master pointers it keeps in blocks of its own. DD Expand 1.1 finds the screen's size by calling InitGraf with A5 pointing into a stack frame, then puts A5 back; QuickDraw goes back to the program's own globals with it. SpeakFile and Speech Tutor open MacinTalk from their own folder, `Sounds:Sound Utilties:MacinTalk:MacinTalk Programs`, but the CD keeps it a folder up; copy it beside them, onto a disk of your own, and SpeakFile speaks and Speech Tutor opens its windows. CheapTalk finds the folder called MacinTalk where it looks for the file, and says so. MacWelcome™ 1.4 shows the message in a text file called WelcomeMessage, which you write yourself; until there is one it keeps looking for it. ScheduleBrain asks for its Schedule Data file, and ModemAnswer 2 sends a command out of a serial port and quits. ResEdit 1.2 and Remove J-Clock stop as ResEdit 1.2d2 and REMOVE*JCLOCK on Volume 1 do. Take a Letter's Geneva 12 Form Letter opens a window full of the letter o, which is what its data fork holds. DoppleMaker and ToMultiFinder show ⌘ in their buttons and titles. RamDisk+ 2.11 installs and opens its own RAM disk driver; it keeps the creation date of the disk its settings were last saved on, and on any other disk it tidies them up and asks at once whether to save them. Speed Check stops with an F-line trap: it uses a dialog it hasn't made, and keeps globals past the space its CODE 0 asks for. Disk Librarian centres its opening message on its widest line, which in the system font, Chicago 12, is 502 pixels wide, 15 more than it allows, so the message starts 7 pixels left of its window and loses a letter or two at each end. TEXT Ranger asks at once for the disk whose TEXT files it's to go through, and Sound->snd 1.2e asks at once for a file to open, in a Standard File dialog of its own. CAMPAIGNER1.2DOCS and TARGETDOC read their text from their own data forks, which are empty on this disc, so their windows stay blank. Desktop Scout finds no Desktop file to look through: neither disc has one. HyperCard 2.0 says the System lacks Courier 12, Geneva 14, Palatino 24 and Helvetica 24, which Volume 1's doesn't have, and opens its Home stack, on a Plus or a Mac II. Some want a Mac II: Robot World runs with `--model ii --depth 8`; on a Plus it stops with a bus error in FillRect, at $C20080. SignalEditor II and TapeOp DEMO run with `--model ii --depth 8` too. V3d.fp says the Plus has no FPU; with `--model ii` it starts, its menus up and no window open. IEdit 1.1's Scrap window starts black: it fills its two scrap icons with ones itself. BigSound VW Player blanks the screen and asks at once, in a Standard File dialog, for a movie to play; pick one from its folder, such as Marbles, and it plays. Mac'N Med Engine, a Helix run-time engine, unloads the segment it's running in, then grows its Apple menu, which lies just below it, with AppendResMenu, and goes on to its menu bar; the demo collection beside it, DemoMac'N Med4.2, opened with File › Open, says it expired at midnight on 1 January 1988. |
| The 500 Mac Games CD | `500MacGames.iso`, 472 shareware and freeware games, demos and game editors in folders by kind, has no System Folder: give it BMUG's with `--system BMUGPDROMVolume1.img` and name each program by its path, as `--app "Cards:Spoydworks Solitaire 1.2 ƒ:Spoydworks Solitaire 1.2"`, with `--host screen`. On the default Plus all but two run without stopping with an error; Orb Mazez and MacCribbage (Color) stop there, and run with `--model ii --depth 8 --size 640x480`, Orb Mazez to its title and MacCribbage to its choice of who deals first. Rescue! makes its offscreen world with `NewGWorld` on a Plus; Poly-Dol passes `UseResFile` a refnum, 2, that's no resource file's (it's the boot volume's extents tree), so it goes on finding its own resources; BrickBounce and Spoydworks Solitaire won't start without the Edition Manager, and Spoydworks, on a Mac II, finds its Games & Decks folder in a dialog that picks a folder (see [What works](#what-works)), then deals its eleven games with any of its sixteen decks; CyberBlast and the Deliverance demo call `RsrcMapEntry` at startup, and CyberBlast plays; and the CyberFlix previews (Jump Raven, Lunicus, Western) read the video card's declaration ROM to see which depths the screen has. On a Mac II in colour, `--model ii --depth 8 --size 640x480`, all but one run without an error: Race Car, a MacFORTH program, has its own handler for `TRAP #15` that takes the exception frame to be the 68000's six bytes, and the 68020 pushes eight, so it runs only on the Plus. MacTriv passes `RectRgn` the address of its rectangle for the region, which isn't a handle in any heap, and macrt leaves it alone. Some want more than a launch: MS BASIC Runtime runs its ADVENTURE program when that's named as the document (`--app "Adventure:ADVENTURE ƒ:ADVENTURE"`), Blocker plays after File › Open Game Map and File › Play the Game, Macinsplat's clicks draw once a weapon is picked from Options, and Ninja Boy, RoadKill and Populous ask for 16 colours. Castles Demo quits as it starts: a byte of its settings, 0 in macrt, takes it down a path that doesn't build its list of sound timers, and its idle loop walks that list until it reads $FFFF, writing -1 over its own class table as it goes, so making its intro's manager fails. |

When you try another, the list of missing calls it prints when it quits
(see [When it stops](#when-it-stops)) is what to report.


## Getting the application to macrt

A Mac file has two forks. The **data fork** is what every other computer
sees. The **resource fork** holds almost everything that makes an
application: its code (`CODE` resources), menus, windows, dialogs, icons
and strings.

If you copy a Mac application to a PC or a Unix machine the ordinary way,
or download it from somewhere that wasn't careful, the resource fork is
lost. What's left is a file of zero bytes, or a little data, that nothing
can run.

So the application has to arrive in a form that carries both forks. macrt
reads all the common ones, and you don't have to say which one you have;
it works it out from the contents:

| Form | Looks like | Where it comes from |
| --- | --- | --- |
| MacBinary I, II or III | `App.bin` | downloads; most Mac transfer programs could write it |
| BinHex 4.0 | `App.hqx` | downloads, Info-Mac and Usenet archives |
| AppleSingle | one file holding both forks | A/UX, some archives |
| AppleDouble | `App` next to `._App`, `.AppleDouble/App` or `App.rsrc` | `unar`, netatalk, macOS copying to a FAT disk |
| Basilisk II and SheepShaver shared folders | `App` next to `.rsrc/App` and `.finf/App` | the emulators' host folder |
| Executor | `App` next to `%App` | Executor's host folder |
| a resource fork on its own | `App.rsrc`, or any file that is one | `DeRez`/`Rez` tooling, resource editors |
| a macOS file | `App` itself, through `App/..namedfork/rsrc` | a Mac running macOS |
| an HFS or MFS disk image | `Disk.dsk`, `.img`, `.image`, `.hfs`, `.toast` | raw and DiskCopy 4.2 floppy images (800K and 1.4MB HFS, 400K MFS), with each sector's 12 tag bytes or without them, HFS CD images, partitioned hard disk images. A CD's image, or any other of 16 MB or more, is mapped rather than read in, and a file's forks are read from it only when they're wanted, so only what's used of it is in memory. |
| a MOOF floppy image | `Disk.moof` | Applesauce, imaging a 400K or 800K floppy's tracks bit by bit |

For AppleDouble and the emulator folders, give macrt the data-fork file
(`App`), and keep the side file where it is.

### Checking a file

```sh
python -m macrt Game.bin --list
```

`--list` prints the file's type and creator and every resource it holds,
then exits. For menus, windows, dialogs, `SIZE` and `vers` resources it
also says what they contain. It's the quickest way to check that an
application arrived with its resource fork: a `CODE` line means there is
68k code to run.

```
$ python -m macrt tests/apps/Hello.bin --list
Hello: application, type 'APPL', creator 'HELO'
  data fork 0 bytes, resource fork 1,007 bytes, 6 resources
  CODE      0       24  purgeable,locked,preload '' jump table, 1 entries
  CODE      1      460  purgeable          'Main'
  MENU    128       40                     Apple: About Hello…, -
  MENU    129       29                     File: Quit
  WIND    128       24                     'Hello', 260x160, procID 0
  SIZE     -1       10                     256K preferred, 128K minimum
```

Each line gives the resource's type, ID, size in bytes, attributes and
name, then what it holds.

If macrt says the file *has no resource fork*, the fork was lost on the way.
Go back to the archive or disk image it came from. If it says the
*resource fork is in its data fork*, something copied the file without
keeping its two forks apart, and a Mac couldn't launch it either. McBug on
both BMUG PD-ROM discs was mastered like this.

### Archives

Most Mac software online is in an archive: `.sit` (StuffIt), `.cpt`
(Compact Pro), `.sea` (self-extracting), `.sit.hqx`, or a `.zip` with a
`__MACOSX` folder. macrt doesn't unpack archives; it tells you when you've
given it one. Unpack it with The Unarchiver, which keeps the resource
forks:

```sh
unar Game.sit.hqx               # decodes the BinHex and unstuffs what's inside
python -m macrt "Game Folder/Game"
```

On Linux and Windows, `unar` writes each resource fork, with the file's
type and creator, as an AppleDouble file named `App.rsrc` next to `App`.
An application's data fork is usually empty, and then `unar` writes only
`App.rsrc`. Give macrt either `App` or `App.rsrc`; both find the same
file. On macOS, `unar` writes real resource forks.

Don't use `unzip` on a zip from a Mac: it leaves the resource forks in the
`__MACOSX` folder, away from their files. `unar` puts them back together.

For example, Vector 2.5, a small program from the Info-Mac archive:

```sh
$ curl -O https://ftp.funet.fi/pub/mac/info-mac/game/arc/vector-25.hqx
$ python -m macrt vector-25.hqx
macrt: vector-25.hqx is a StuffIt archive: unpack it first, for example with The Unarchiver (unar vector-25.hqx)
$ unar vector-25.hqx
$ ls "vect_250 folder"
Vector 2.5 Doc  Vector 2.5.rsrc
$ python -m macrt "vect_250 folder/Vector 2.5"
```

### Disk images

Many collections come as disk images: floppies, CD-ROMs and hard disks.
macrt reads HFS and MFS volumes directly, so there's nothing to extract:

```sh
python -m macrt "System 6.0.8.dsk"                  # a disk with one application
python -m macrt "System 6.0.8.dsk" --app TeachText
python -m macrt Tools.img --app "Tools:Disk Tools:Disk First Aid"
python -m macrt Paint.dsk                           # a 400K MFS floppy from 1984
```

`--app` takes the application's name, or its Mac path with folders
separated by colons, starting from the disk's name or from any folder
below it. Names are matched without regard to case. Run a disk that holds
several applications without `--app`, and macrt lists them:

```
$ python -m macrt mac6-0-8.dsk
macrt: mac6-0-8.dsk holds 7 applications; pick one with --app:
  Mac System 6.0.8:Applications:Microsoft Excel:Microsoft Excel
  Mac System 6.0.8:Games:Creepy Castle:Creepy Castle™
  Mac System 6.0.8:Games:Operation Tsunami:Operation Tsuanmi
  Mac System 6.0.8:LabelWriter II Folder:LabelWriter II App
  Mac System 6.0.8:LabelWriter II Folder:TeachText
  Mac System 6.0.8:System Folder:PrintMonitor
  Mac System 6.0.8:TeachText
```

When two applications have the same name, as the two TeachTexts do here,
`--app TeachText` takes the one nearest the top of the disk
(`Mac System 6.0.8:TeachText`). Give more of the path to get the other:
`--app "LabelWriter II Folder:TeachText"`.

macrt reads raw images and DiskCopy 4.2 images, including images of
partitioned disks (an Apple partition map with an HFS partition).

It also reads Applesauce's MOOF images of 400K and 800K floppies. These
keep each track as the bits the drive reads, as the moof-a-day
collection keeps its floppies; macrt decodes them back to sectors, the
way a Mac's floppy drive does, when it opens one. A sector that can't be
read is left as zeros, and a program that reads it through the floppy disk
driver is told it can't be read, as on a Mac. A few keep a track instead
as the flux changes Applesauce timed going by, where bits can't say what's
there; macrt reads those as a Mac's floppy controller would. MOOF images
of 1.4MB floppies aren't read: convert them to a raw image first.

A raw or DiskCopy image of a 400K or 800K floppy has only the sectors,
not the tracks, and macrt gives the drive the tracks a Mac's format
would have written for them: each sector's address field and data
field, two sectors apart round the track. A program that reads the disk
itself finds what it would on a copy of the disk: MacGolf's copy
protection reads a sector with a routine of its own that reads only the
sector's marks, and leaves the sector where it was. Since the image
didn't keep the marks, the ROM's routine reads a data field with whatever
marks a program gives it: The Slide Show Magician reads its key file
through marks its master disk has there.

MFS disks are the 400K floppies of System 1 to 4, from 1984 to 1987: the
first MacPaint and MacWrite disks, and most early games, came on them.
MFS has no folders of its own. The folders you saw in the Finder were kept
in its Desktop file, and applications never saw them, so macrt puts every
file at the top of the disk and `--app` takes just the name. An
application on an MFS disk sees an ordinary HFS volume, as it would have
on a Mac Plus.

A few early games took the Finder's place on their disk, so that a Mac
started from it went straight into the game. Given a disk without
`--app`, macrt runs nothing itself: it opens a Finder window over the
disk's contents (see [Several applications at once](#several-applications-at-once)),
where the program the disk starts up into, as its boot blocks name it —
the game on such a disk — is there to double-click like anything else.

Some early programs check that they're on their original floppy, by
reading marks a copier can't copy. From a MOOF image, which keeps what's
on each track, a check that reads through the floppy disk driver gets
what's on the original, and so does one that puts its own routine in the
driver's place to read past a sector's address field, as Excel 1.0 does,
or to give the ROM's routine marks of its own to look for, as Dollars and
$ense and PFS:FILE do. A check that times the disk as it turns, through the ROM's
routines that find each sector's address field as it comes round and
step the head, as Mac Attack's does, sees the original's timing: the
disk turns at the speed its zone of tracks did. Where a track goes on long with no flux change,
the drive reads noise there, different bits each time, and a check that
reads it twice, as Q-Sheet's does, sees that it's the original; a few zeros
together the drive reads as written, so a check that counts a turn of a
track whose bytes are further apart than a disk's own, as The Ancient Art
of War's does, counts what the original gives. A check
that steps the head itself and counts the bytes the floppy controller
reads from the track it moved to, as PageMaker's does a track in from
its key sector, sees them go by as the disk turns, and one that times
them with the VIA's timer, as Jazz's does, counts what the original
gives: the VIA and the drives keep one clock. A check whose own routine
reads a sector bit by bit as the floppy controller shifts them in, as
Shufflepuck Cafe's does, sees the original's bits too. It stops the
shifting for as long as its own instructions take, and macrt counts what
each instruction would take a Mac, so the same bits go by unread as on
the original. A check with its own routine to find a sector's address
field, as Dragonworld's has, is called for each sector the driver
reads. A key track whose flux changes come a bit cell and a half apart,
as Fraction Action's, MathTalk's and KidTalk's do, reads differently
each time, as on the original: the floppy controller reads each such
change as one cell after the last or two, as it comes a little early or
late, and their check reads the track twice and sees the difference that
a copy, written as bits, can't have. A check that steps the head through
the drive's registers, waits through the ROM's WakeUp and expects a
given sector next, as Moebius's does, sees the skew from one track to
the next that the original has: the drive says at once that a step is
over, and the disk driver's step and settle times, which WakeUp waits
for, are 12 and 30 ms. Those are macrt's choice, within what such a check
allows, not times known from the ROM. Other checks that
drive the floppy drive's hardware themselves still fail: the program
shows its own "damaged disk" or "not an original" alert, or asks for its
master disk.

macrt can't read compressed images yet: NDIF (DiskCopy 6) and UDIF
(`.dmg`, `.smi`). Convert them to a raw image first.

### Where to find software

Use software you have the right to run. Apple's own system disks, such as
System 6.0.8, are a good first test: they include TeachText and a few
small utilities. The Info-Mac archive, mirrored for example at
`https://ftp.funet.fi/pub/mac/info-mac/`, holds thousands of freeware and
shareware programs as `.hqx` files: unpack them with `unar` as above.
Small black-and-white programs are the likeliest to run. The Internet
Archive keeps images of many original 400K floppies, as raw `.dsk` or
DiskCopy images that macrt opens as they are, and as MOOF images in its
moof-a-day collection, about 150 early Mac titles. Its Macintosh Software
Library holds many more, as DiskCopy images (`.dc42`, `.img`) or raw
`.dsk` files; where an item has several, one named `00playable` is the
disk to start from.


## Running it

```sh
python -m macrt FILE... [--app NAME]... [options]
```

| Option | What it does |
| --- | --- |
| `--app NAME` | Picks the application on a disk image, by name or Mac path. A document's name launches the application that made it, with the document open (see [Opening a document](#opening-a-document)). Repeat it to run several. |
| `--list` | Lists the file's resources and exits. |
| `--view` | Shows the application's menus, windows and dialogs from its resources, without running its code. Useful when the code won't run. |
| `--trace-traps` | Logs every Toolbox and OS trap the application calls. |
| `--system FILE` | Uses a real System file, or a disk image holding one, in place of macrt's own small one. See below. |
| `--host desktop` | Each Mac window is a window on your desktop, with one menu bar for the front application. This is the default. |
| `--host screen` | Everything is drawn inside one window that is the Mac's screen. |
| `--menubar global` | One menu bar, the front application's. This is the default. |
| `--menubar window` | A menu bar under each window's title bar. |
| `--size WxH` | The Mac screen's size, such as `512x342` or `640x480`. The default is your screen's size with `--host desktop`, and 640×480 with `--host screen`. |
| `--speed N` | Runs 68k code at about N times a Mac Plus's speed, by the cycles its instructions would take a 68000. Games from 1984 time themselves by how fast the processor goes, and are unplayable at full speed; `--speed 1` is a Mac Plus. The Toolbox's routines, which macrt runs itself, aren't slowed, and above about 3 the counting can't keep up. The default is as fast as it goes. |
| `--memory K` | Gives the application K kilobytes of memory, in place of what its `SIZE` resource asks for, as the memory size in the Finder's Get Info does. A `SIZE` resource from before MultiFinder can ask for too little: the Finder of the time gave an application all the memory there was. A control panel runs in the memory of the program that hosts it, so its size goes to the application it launches from its own file, as After Dark 4.0's Demo does. |
| `--no-sound` | Keeps the Mac's sound off your computer's speakers. See [Sound](#sound). |
| `--record-sound FILE.wav` | Writes the Mac's sound to a WAV file as it plays, as well. |
| `--model plus` | Says the Mac is a Mac Plus, with a 68000 and no floating-point unit. This is the default. Programs from before the Mac II need it: a 68000's exception frames are smaller than a 68020's, and MacWrite 4.5 pops its own. |
| `--model ii` | Says the Mac is a Mac II, with a 68020 and a 68881, for a program that needs one. The instructions run are the same either way. Some games pick how to draw by the processor: on a 68000 they draw straight into the screen's memory as if it were a 512×342 Mac's, which on a bigger screen puts their picture in the wrong place. Give them `--model ii`, or `--size 512x342`. A Mac II's screen is in colour: see `--depth`. |
| `--depth N` | With `--model ii`, the screen's bits a pixel: 1, 2, 4 or 8 for that many bits of an index into the screen's colour table, 16 or 32 for colours themselves. The default is 8, 256 colours. A Mac Plus's is 1, black and white. |
| `--row-bytes N` | How many bytes apart the screen's rows are in its memory at the depth it starts at, as if its memory were wider than what shows; when a program changes the depth, they're as many pixels apart as before (with `--depth 8 --row-bytes 1024`, 128 bytes at 1 bit a pixel, 512 at 4). QuickDraw says how far apart they are (`screenBits.rowBytes`, and the `rowBytes` of the screen's `PixMap`), and most programs that draw straight into the screen ask it; a few take the rows to be some fixed number of bytes apart instead, and draw each row in the wrong place unless the screen's are so far apart. The default is as few as a row needs: 80 for a 640-pixel row at 1 bit a pixel, 640 at 8. |
| `--classic-menus` | Menus stay open only while the mouse button is held, as before System 7. |
| `--rainbow` | Shows the striped Apple logo in the menu bar. |

Quit an application from its own File menu, or close macrt. Ctrl+C in the
terminal quits macrt and everything running in it.

On a PC keyboard, **Ctrl** is the Mac's Command key (⌘), **Alt** is Option,
and the Windows or Super key is Control. On a Mac keyboard, the keys are
the Mac's own.

The keys have the key codes of the modelled Mac's keyboard. A Mac Plus's
arrow keys are $46, $42, $4D and $48, the codes its keypad's +, *, / and =
send with Shift; a Mac II's ADB keyboard has $7B to $7E for them. The
keypad's keys have codes of their own, apart from the same digits on the
main row, for games that steer by the keypad. While an arrow key is down,
it is in the `KeyMap` by both keyboards' codes, since games written for
the one keyboard read the other's.

### Several applications at once

```sh
python -m macrt Hello.bin Dialogs.bin
python -m macrt mac6-0-8.dsk --app TeachText --app "Creepy Castle™"
```

Every file you name is launched, in order. When disk images are among
them, each `--app` is looked for on the images in turn and taken from the
first one that has it. Without `--app`, nothing is launched from an
image: each one opens in a Finder window, as System 6's Finder would show
the disk — double-click an application to run it (its launch is as if it
had been named on the command line, so several can be started from the
one window), a document to open it with the application that made it, or
a folder to open a window of that folder too. The window stays up, and
its close box closes it, like a real Finder window's.

An image nothing is launched from, one with no application on it or, with
`--app`, none of the names, is a disk of documents. Every image is in a
drive from the start, the first in the internal drive, so a game on two
floppies finds its second disk when it asks for it by name, or puts it in
through a volume control block of its own, as Uninvited does:

```sh
python -m macrt "BDC 1.moof" "BDC 2.moof" --app "Beyond Dark Castle" --host screen
```

A program that ejects a floppy gets it back a second later, as if you had
put it back in. The drive then posts a disk-inserted event, and the disk
is mounted again. A game that ejects its disk and waits for a disk, as
Seven Cities of Gold does for its map disk, goes on with the same disk.

A game on more disks than there are drives ejects a disk, unmounts it
(`_UnmountVol`) and asks for another. Then a dialog asks which of the
disk images you named goes in that drive, the next one in turn chosen.
Insert puts in the disk you choose, and Put Back puts back the disk that
came out. If the disk you choose is in another drive, it comes out of
that drive, and the disk it replaces goes in there, unmounted. Without a
display to ask on, the next disk in turn goes in. Wizardry VI is played
this way:

```sh
python -m macrt A.moof B.moof C.moof D.moof E.moof F.moof --app Bane --host screen
```

The applications run side by side, as under MultiFinder. Each has its own
memory partition, A5 world, low-memory globals and menu bar. The menu bar
belongs to the front application, and clicking another application's
window brings that application to the front.

An application that launches another one (with `_Launch`) gets it the same
way. A `_Launch` without `launchContinue` replaces the application, as on a
Mac. System 7's `LaunchApplication` works too: its parameter block names
the application with an `FSSpec`, and gets back the new process's serial
number and the partition sizes from its `SIZE` resource.

### Opening a document

`--app` can name a document on a disk image instead of an application.
macrt then launches the application that made it, the one whose creator
the document has, from the same disk if it's there or else from the other
images, and opens the document with it, as double-clicking the document
does in the Finder. Mac Pro Football's game is a document of this kind:
a program for Microsoft BASIC's run-time, which is the application.

```sh
python -m macrt "Mac Pro Football.dc42" "Team Files.dc42" --app MSFL --host screen
```

The application finds the document in its Finder information, the handle
that `_CountAppFiles` and `_GetAppFiles` read (also at 16(A5)), with the
message to open it rather than print it. Each document is listed with a
working directory for the folder it's in. A System 7 application that
handles Apple events gets an Open Documents event for it instead of Open
Application.

A HyperCard stack is a document of HyperCard's. The Manhole's disk has
only its stacks, so give HyperCard's disk after it:

```sh
python -m macrt TheManhole.img Culture.img --app "the Manhole" --host screen
```

Documents made by the same application, named one after another, open in
one launch of it, as when they're selected together in the Finder. An
`--app` naming the application itself is a launch of its own, with no
documents, unless documents follow it: a document whose creator is an
application named before it opens in that one. This picks which of two
HyperCards opens a stack:

```sh
python -m macrt StrangerThings.img HypercardBootVolume.img \
    --app "HyperCard 2.4:HyperCard" --app "Stranger Things" --host screen
```

### Documents and saving

An application starts in its own folder, as when the Finder opens it, and
its Open and Save dialogs start there too. These are macrt's own dialogs,
not the application's. Where a file it saves ends up depends on where the
application came from:

| The application came from | What happens to files it writes |
| --- | --- |
| a folder on your computer | They're written into that folder. A file read as MacBinary or AppleSingle is written back the same way. Any other file is written as its data fork under its own name. Its resource fork, type and creator go in the side file it already had, such as `unar`'s `name.rsrc`, or for a new file in an AppleDouble `._name`. macrt reads all of these back the next time. |
| a disk image | The changes are kept in memory and lost when macrt quits. The image file itself is never changed. |

A BinHex file is text, not a Mac file, so macrt treats it as locked. Some
applications keep their settings in their own resource fork, and can't
save them while they run from a `.hqx`. Unpack it with `unar` first.

Applications also see a startup disk called **Macintosh HD** with a System
Folder. Preferences files they write there last only until macrt quits.

### Printing

macrt's printer prints to a PDF. Page Setup and Print show macrt's own
dialogs rather than a printer driver's:

- **Page Setup** picks the paper (US Letter, US Legal or A4) and whether
  the page is tall or wide.
- **Print** picks all the pages or a range of them, the number of copies,
  and the PDF to save. It's named after the front window, in the folder
  you started macrt from (`Untitled.pdf`, or `Untitled 2.pdf` if that's
  taken). Choose… picks another place.

When the PDF is written, macrt says so:

```
macrt: printed 2 pages to /home/you/Untitled.pdf
```

The printer says it's an ImageWriter that prints at 72 dots per inch, so
every application draws its pages with QuickDraw, as it does on the screen.
The PDF's pages are black and white at 288 dots per inch. Applications from
1984 find the printer through their own glue code, as they did on a Mac
(see [What works](#what-works)). MacPaint prints a bitmap at a time,
straight to the printer driver, and shows no Print dialog. Its PDF gets the
name the dialog would have given it. The printer is the same with a real
System file (`--system`), whose own printer drivers would drive a serial
port.

### A real System file

Without `--system`, applications run with macrt's own small System file.
It has what applications most often ask a System file for: the standard
window, menu and control definitions, the packages (`PACK` 0 to 15), the
stop, note and caution icons (`ICON` 0 to 2), the standard cursors
(`CURS` 1 to 4: I-beam, cross, plus and watch) and the US international
resources (`INTL` 0 and 1). It also has the pattern list (`PAT#` 0) that
paint programs show as their palette, and the desktop's gray and light
gray (`PAT ` 16 and 17). Its icons, cursors and patterns are
drawn for macrt. Some applications look for resources that only a real
System file has, such as other icons, strings (`STR#`), the fonts
themselves and the Script Manager's `itl` resources.

When the applications come from a disk image that has a System file of
its own, macrt's System gets that file's fonts of the families it hasn't
got, up to 128K of them: programs drew in the fonts of the System they
started up from, and some brought their own there, as Mac Attack's tanks
and landscape are characters in fonts of its disk's System. Fonts of the
standard families stay macrt's, but the monospaced ones, Monaco and
Courier, are measured with the widths of that System's strikes of them,
as with a real System file (below): Hacker types each letter in Monaco 9
and its cursor after it, then backs up six pixels, Monaco's width, to
type the next letter over the cursor. And lines in a standard family
are as far apart as that System's strikes of it set them: `GetFontInfo`
gives their ascent, descent and leading rather than those of your
computer's font, a 16-pixel line for Chicago 12, so that The Venice
Project's prompt goes under the box it asks you to type in, not across
it.

It gets that System's drivers too, those named with a period, such as
a speech driver, and the resources they load that aren't of the kinds a
System file of Apple's has, up to 128K: Speller Bee speaks its words
through the `.SAY` driver its disk's System has, which loads its code
from `OVLY` resources there.

And it gets that System's decompressors, its `dcmp` resources. Many of
System 7's resources are compressed, as System 7.5's utilities' are:
macrt expands those it can itself, and for the others runs the `dcmp`
that the resource's header names, on the 68k, as the Resource Manager
did.

The System version that Gestalt, `SysEnvirons` and the low-memory
`SysVersion` give is that System's, from its `vers` resource, or a real
System file's, given with `--system`, from 7.0.1 to 7.6.1: System 7.5's
utilities look for 7.5. Without one, or with an earlier System, it's
7.0.1.

For everything else, give them a real System file:

```sh
python -m macrt Game.bin --system "System 6.0.8.dsk"
python -m macrt Game.bin --system "System Folder/System"
```

The System file's resources then sit at the bottom of every
application's resource chain, as on a Mac, and its desk accessories are
in the Apple menu. Chicago, Geneva and the other standard fonts are
still drawn with your computer's fonts, but measured with the widths of
the System file's own bitmap fonts, at the sizes it has them, so that
text lines up as it did on a Mac. The fonts in the suitcases in the
Fonts folder beside the System file are the System's too, up to 192K of
their bitmap fonts (not their TrueType outlines): System 7.5's System
file has Geneva only at 9 and 12 points, and Courier and Helvetica only
in that folder, which HyperCard Player's stacks ask for. (A standard
font the application carries in its own file, at the size asked for, is drawn from its
bitmap, as Balance of Power's New York is, and Gemstone Warrior's
Chicago, which it makes the application font by setting `ApFontID`. An
application's own Chicago 12 is the one its menus are drawn in, as on a
Mac: The Fool's Errand's menu titles are Roman numerals in its font.)
Its 68k definition procedures and packages aren't run: windows, menus and
the standard controls are always drawn by macrt, and the package calls
are always macrt's. Anything above
that the real System file lacks, macrt adds.

A System 7 file's System heap has room to grow, as a real one's has
("the system heap expands dynamically to meet your request", Inside
Macintosh: Memory, "Allocating Memory at Startup Time"): up to 1.5 MB,
with applications' partitions above it, where macrt's own System keeps
to 512K. HomePublisher marks its code segments to be loaded into the
System heap, and couldn't start in 512K.

### Control panels

A control panel, a `cdev` file in the Control Panels folder, runs as
System 7's Finder ran one: in a window of its own, with the panel's code
called for whatever happens there (Inside Macintosh: More Macintosh
Toolbox, Control Panels). Name it with `--app`, from a disk with
System 7 on it:

```sh
python -m macrt "System 7.5.3.img" --model ii --depth 8 --size 640x480 \
    --app "System Folder:Control Panels:Date & Time"
```

The window is made of the rectangles in the panel's `nrct` resource, its
text in the font its `finf` names, or in 9-point Geneva, the application
font, without one. Its close box, File › Close or
File › Quit closes it, and the Edit menu's commands go to the panel. A
panel whose `mach` resource says to ask it whether it can run on this
Macintosh is asked, and one that says no isn't opened: macrt says it
"can't be used with this Macintosh".

A panel with `INIT` resources of its own, the code a Mac runs from it as
it starts up, has them run first, each called as at startup (Inside
Macintosh IV, The System Resource File, "Initialization Resources").
One that stops with a system error is left out, as if it hadn't been
loaded: the traps it patched are put back, and what it gave Gestalt
goes. If the panel then stops as it opens, or later in code its `INIT`
resources left behind, it's opened again without them, as on a Mac
started with its extensions off, and macrt's log says so. Traps an
`INIT` patched with code in the system heap stay patched for the
applications launched after; a patch in the panel's own memory goes
when the panel closes. Extensions that are files of their own aren't
run.

From System 7.5.3's disk, with the options above:

| Control panel | What happens |
| --- | --- |
| Color, Date & Time, Easy Access, Extensions Manager, General Controls, Keyboard, Map, Memory, Mouse, Numbers, Sound, Startup Disk, Text | Run. Sound lists the alert sounds, and its pop-up menu switches to its other views, which are components in its own file (see [What works](#what-works)). Startup Disk lists the disks. |
| Apple Menu Options, CloseView, WindowShade | Run, their `INIT` resources run first, and open to their settings. |
| AutoRemounter, Control Strip, Macintosh Easy Open, PC Exchange | Open, but each says first that it isn't installed: their `INIT` resources call on parts of the System that macrt hasn't got, and stop, so the panel runs without them. |
| Speech | Opens, but says it needs text-to-speech or speech recognition software, which macrt hasn't got. |
| Launcher | Opens its window, with nothing in it. It shows what is in the Launcher Items folder of the System Folder in use, which is macrt's own on Macintosh HD, not the disk's, so it makes an empty one. |
| 601 Processor Upgrade, Auto Power On/Off, Brightness, Monitors, Password Security, PowerBook, PowerBook Display, PowerBook Setup, Power Macintosh Card, Screen, Serial Switch, Trackpad | macrt says each can't be used with this Macintosh, a Mac II with macrt's screen. |
| File Sharing Monitor, Labels, Sharing Setup, Users & Groups, Views | Refused: they have no code of their own for macrt to run. |
| Desktop Patterns, Energy Saver, Monitors & Sound | Aren't `cdev` files. Desktop Patterns is an application, and runs as one (see [Tried so far](#tried-so-far)). |

A control panel on a disk of its own runs the same way. ScreenChooser 3.1
(`ScreenChooser.img --app ScreenChooser`, with the options above) shows
its shareware notice, and OK opens its General Options: its check boxes
check and uncheck, its Quick Help says what each is for, and Help shows
its user's guide. Backdropper and Set Backdrop, beside it, say
ScreenChooser isn't running: they're programs of their own, and
ScreenChooser's `INIT` resources run only as its control panel opens.

After Dark 2 (`AfterDark.img --app "After Dark"`, with the options
above) opens with its modules listed, Flying Toasters picked. Demo
shows the module, its toasters flying across the screen, and a click
brings the panel back.

After Dark 3.0 (`AfterDark32.img --app "System Folder:Control
Panels:After Dark 3.0"`, with the options above) says first that it
can't run, that it needs System 6.0.7 and MultiFinder: its `INIT`
resources look for MultiFinder by asking `GetTrapAddress` for
`_OSDispatch`, which macrt says isn't there (see [What
works](#what-works)). Its panel runs all the same. It says the copy is
unregistered, and OK opens it with its modules listed, Flying Toasters
Pro picked. Demo shows the module, its toasters flying across the
screen around the panel's settings. The modules' libraries go in
temporary memory.

After Dark 4.0's demo disk (`AfterDark40.img --app "System
Folder:Control Panels:After Dark 9" --memory 4096`, with the options
above) says first, for the same reason, that it needs System 7.0 or
later, and its panel opens with its modules listed. Demo launches the
application in the panel's own file, and the panel quits, as a program
that calls `Launch` does. Flying Toasters needs 256 colours, and about
3.3 MB for its toasters, which it takes from the application's heap
when there's no `_OSDispatch` for temporary memory. That application's
`SIZE` resource asks for 600K, and the module says it's out of memory,
so `--memory` gives the file a bigger memory size, as Get Info would.
With it, the toasters fly, the words of their song along the bottom of
the screen, with the module's settings in front.

The Simpsons Screen Saver's disk (`AfterDarkSimpsons.img --app "System
Folder:Control Panels:After Dark 9"`, with the options above) has
After Dark 4.0's panel with modules of its own, in the Simpsons folder
of the panel's pop-up menu. Their library takes temporary memory
through `_OSDispatch`, so they run without `--memory`. Demo shows
Chalkboard's lines being written on the board, Lisa's Mood Swings'
Lisa playing her saxophone, and Itchy and Scratchy on a desktop of
their own. That desktop's folders and Trash are the System's icons:
with `--system` given the same disk they show, and with macrt's own
System only their names do. Itchy & Scratchy asks for 2 MB of
temporary memory at once. With `--memory 4096` there's less than that
outside the panel's partition, and its screen stays black. The
folder's other modules run too: How to Draw sketches Maggie, Homer
Eats eats the desktop from the bottom up, Physics bounces the family's
heads, Simpsons Trivia asks its questions, and Snowball I floats on
clouds with a halo.

### Games from 1984

The first Macintosh games often go around the Toolbox. They draw
straight into the screen, read the mouse button from the hardware, and
keep time by the processor's speed or by the VIA's timers. macrt gives
them what they reach for:

- **The screen buffer.** The bitmap at `ScrnBase` mirrors the windows.
  What QuickDraw draws is written there, and what a program writes there
  shows in the window it lands on, at its next trap or within a tick if
  it calls none. What a program writes where no window is shows on the
  desk, which only `--host screen` has.
- **A Mac 512K's screen.** With `--size 512x342` the screen buffer is at
  `$7A700`, where a 512K or a Plus has it, for games that write there
  without asking `ScrnBase`. Most games from 1984 and 1985 expect that
  screen. Its alternate buffer is `$8000` below, at `$72700`. An
  application launched with `Launch`'s page option finds it in
  `CurPageOption`, and while the VIA's `vPage2` bit is clear the desk and
  the menu bar show the alternate buffer rather than the main one. The
  windows go on showing what's drawn in them. A Plus's RAM repeats through
  its 4 MB of addresses, so the screens are at `$3FA700` and `$3F2700` as
  well, and Apache Strike's flight writes them there. `BufPtr`, the top of what an
  application may use, and `ScrnBase` are each application's own. For an
  ordinary launch both are the screen's base, `$7A700`. An application
  launched with the alternate screen (a negative page option) gets the
  memory a Plus with 4 MB gives it: its partition ends just under
  `$3F2700`, with its A5 world under the alternate screen, and its
  `ScrnBase` and `BufPtr` are both `$3FA700`, as are its QuickDraw's
  `screenBits.baseAddr` and the bit maps of the ports and windows it
  opens. MacRacquetball launches itself again until `BufPtr` is far
  enough over its A5, Arkanoid's demo stops unless `BufPtr` is
  `ScrnBase`, and Yeager's AFT launches itself again until its A5 is
  under `screenBits.baseAddr` less `$8000`. When that room is taken, as
  when Arkanoid's launcher, which is in it, launches the game, the
  partition goes lower, with its top `$8000` kept for the alternate
  buffers, and gets the same `ScrnBase` and `BufPtr`. A partition above
  `$400000` has `BufPtr` at its own top and `ScrnBase` at `$7A700`.
- **The VIA**, at `$EFE1FE`: the mouse button, the vertical blanking flag
  at each tick, the one-second flag, the two timers, and which screen
  buffer is shown. Above it, where a Plus looks for a test ROM, there is
  none, and reading there is no bus error.
- **The exception vectors.** What the System leaves in them is in a page
  of ROM over the top of RAM, at `ROMBase`, as on a Mac. A program can put
  its own handler in any of them, for a `TRAP`, dividing by zero or `CHK`,
  and it comes back past the instruction that raised it. A handler for the
  VIA's interrupts, at `$64`, is interrupted at each tick and once a
  second, from the next tick on; it goes on to the ROM's, as
  Flight Simulator's does, to clear them. When the program quits, the
  vectors it took are the System's again. The A-line vector, `$28`, holds
  the ROM's trap dispatcher, and the start-up code that puts it there is
  in the ROM too, `LEA` then `MOVE.L A0,$28`, for programs such as Lotus
  Jazz that look for it there to put it back; a jump to the dispatcher
  with a trap's address stacked does the trap.
- **The stack.** An application gets 32K of stack between `ApplLimit` and
  `CurStackBase`, and `DefltStack` says so: The Fool's Errand takes what
  that falls short of 32K from its heap. `ReserveMem` grows the heap
  toward `ApplLimit` for what it reserves, and all the way when that's not
  enough, as a 64K ROM's does for programs that ask for more than there is
  in place of `MaxApplZone`.
- **The drives.** A floppy disk's image is in drive 1, the internal
  drive, with the floppy disk driver's reference number, -5. macrt's own
  disk is a hard disk, from drive 3. Flight Simulator looks for its disk
  in drive 1. Each drive is in the drive queue at `DrvQHdr`, with the
  flags before its element: a floppy drive's disk in place, a hard
  disk's 8 (it can't be ejected).
- **The floppy disk driver**, `.Sony`. `Read` and `Write` with reference
  number -5 read and write the disk in drive 1 or 2 by sector, as copy
  protection and disk tools do, with each sector's 12-byte tag at
  `TagData` and in the buffer `Control` 8 gives it; `Status` 8 is the
  drive's. What's written stays in memory, as with the File Manager's
  writes to a disk image. A program can put its own routine in the 64K
  ROM's `RdData` vector to read what's on the disk after a sector's
  address field; macrt calls it with a MOOF image's bytes there coming in
  through the IWM, the floppy controller, at `$DFE1FF`, and with A3
  pointing at the ROM's table of the six bits each byte from the disk
  stands for (indexed by the byte, $FF for one that stands for none), as
  MacGammon's routine expects. The routine can
  go on to the ROM's, which `RdData` held, with A1 pointing at the five
  marks the data field begins and ends with: it reads the field into the
  buffer at A0, or compares it with the buffer while `DskVerify` is set.
- **What the Event Manager keeps in low memory:** the mouse (`Mouse` and
  `RawMouse`; and `MTemp`, which counts its movement up, for a program
  that clears it to see how far it has moved) and its button (`MBState`),
  the keys held down (`KeyMap`, which `GetKeys` reads; an arrow key by
  both a Mac Plus's code and ADB's) and the last key
  pressed (`KeyLast`, `KeyTime`). They follow the mouse with the button up
  too. A program can move the mouse itself, writing `RawMouse` and setting
  `CrsrNew`, and macrt's cursor task copies it to `Mouse` at the next tick
  and clears `CrsrNew`, which Pirates! waits for. While the program has
  the cursor hidden, the mouse stays where it put it and goes on from
  there as the host's pointer moves, which is how Crystal Quest steers;
  with the cursor showing, it's back under the pointer when that moves.
- **`--speed`**, for games that run as fast as the processor goes. A
  modern computer runs them hundreds of times too fast; `--speed 1` is
  about a Mac Plus. Each instruction is counted by the cycles it would
  take a 68000, and the 68k code is held to the 6 million a second a
  Plus's gets through, its RAM shared with the video and the sound. A
  game that times its frames by the ticks, as Downhill Racer does, sees
  them take as long as on a Plus. `TickCount` is what `Ticks` holds, as
  the ROM's is, and `Ticks` changes at each tick, so a program that reads
  one and then the other sees the same count.

So a game on a 400K floppy runs like this:

```sh
python -m macrt "Mac 128K Games Vol. 1/Frogger.DSK" --host screen --size 512x342 --speed 1
```

A game that doesn't use menus may draw over the menu bar, in the top 20
rows of the screen. As on a Mac, the bar is in the screen buffer, so what
the game draws there, white or black, shows over the bar until it calls
`DrawMenuBar`. A window that reaches up over the bar doesn't draw there,
as its visRgn leaves out the bar, as the desk (`GrayRgn`) does. A game
that means its window to cover the bar puts the bar back in the visRgn
itself, as Indiana Jones and the Last Crusade does, and then what it
draws there shows over the bar in the same way. A game's windows go on
showing the main screen buffer while the VIA shows the alternate one.

### Sound

A Mac 128K, 512K or Plus makes its sound from a buffer in memory, at
`SoundBase`: at each tick, 370 samples from it go to the speaker, while
the VIA has the speaker on, at the volume in the VIA's low bits. macrt
plays the buffer the same way, through your computer's sound output.
The volume starts at 7, the loudest, in the VIA, in `SdVolume` and in
parameter RAM. What's in the buffer comes from three places:

- **The Sound Driver**, `.Sound`, reference number -4. `StartSound`, a
  `Write` to it, plays a sound through one of its three synthesizers:
  square-wave, tones of a pitch, a loudness and a length; four-tone,
  four waveforms played together, as MusicWorks plays its songs; and
  free-form, samples at a rate. An asynchronous sound plays while the
  program goes on, those after it waiting their turn, and its completion
  routine is called when it's done. `StopSound`, a `KillIO`, stops them.
- **The Sound Manager** (Inside Macintosh V), which System 6 and 7
  programs call: `SndPlay` plays a `'snd '` resource, and sound channels
  take commands from the program, `SndDoCommand` queueing them and
  `SndDoImmediate` sending them at once. At each tick, each channel's
  synthesizer makes the next frame, and they're added to the Sound
  Driver's. The note synthesizer plays notes, from a sine to a square
  wave as the timbre goes up; the wave table synthesizer plays the
  program's own waveform; the sampled sound synthesizer plays sound
  headers' samples (`bufferCmd`), and notes on an instrument from one
  (`soundCmd`), looped while the note lasts. `waitCmd`, `callBackCmd`,
  `pauseCmd`, `ampCmd`, `rateCmd` and the rest are there, and so are
  modifiers, the program's own, from `SndAddModifier`. `SndPlay` with no
  channel, or not asynchronously, waits for its sound to end, as does
  `SndDisposeChannel` without `quietNow`, with the ticks going on.
  MineSweeper, Glider, Glypha, Shadow Keep and Tesserae play their sounds
  this way. Play from disk, `SndStartFilePlay`, plays an AIFF or AIFF-C
  file the program has open, or the sampled sound of a `'snd '`
  resource, all of it or the seconds its audio selection says;
  `SndPauseFilePlay` pauses and resumes it, `SndStopFilePlay` stops it or
  waits for its end, `SndChannelStatus` gives its times, and the
  program's completion routine is called when it ends, however it ends.
- **The program itself**, writing its samples into the buffer at each
  tick, as Dark Castle, Crystal Quest and SmoothTalker's speech do.

On a Mac II, a program can also write its samples to the Apple Sound
Chip, at the address in `ASCBase`, as Digital Messiah does with its
music, 370 of them at each tick from its VBL task. What it writes to the
chip's first 1K goes into one queue of samples and its second 1K into
another, each keeping up to 1K; at each tick the speaker plays the next
370 from them, the two averaged while both have some, with the sound
buffer's. macrt's Mac Plus has no chip, and its `ASCBase` is 0.

`--no-sound` keeps the sound off your speakers, and `--record-sound
FILE.wav` writes it to a WAV file as well: 8-bit mono, 22,200 samples a
second.

How it differs from a Mac:

- macrt's ticks are 60 a second, a Mac's 60.15, so the samples play at
  22,200 a second rather than 22,255, and the Sound Driver's tones are 4
  cents flat.
- The ticks, and so the sound, go on while the application's code runs
  and while it waits: in `Delay`, in `WaitNextEvent` with time to sleep,
  in a menu, a modal dialog or a window being dragged. Its VBL tasks and
  Time Manager tasks run at those ticks too, but the VIA's interrupts
  wait for the program's own code to run again, since they would come in
  the middle of the call it waits in. Under MultiFinder, the ticks that
  run are those of the application that has the processor, or had it
  last, each application's VBL tasks being its own.
- The alternate sound buffer isn't played, and timer 1 doesn't turn the
  speaker on and off by itself, as some programs have it do through the
  VIA.
- `SysBeep` is your computer's own beep. MIDI, which goes out through
  the serial ports, plays nothing.
- The Sound Manager's synthesizers stand in for Apple's `'snth'`
  resources, which aren't run, and nor are modifiers that are resources.
  Its sounds are the Plus's, in one channel, so stereo's sides are added
  together; compressed sounds are silent, as is what `Exp1to3` and
  `Exp1to6` expand MACE to, and `syncCmd` doesn't wait for
  other channels. A channel's commands past its full queue wait outside
  it, so a program never waits for room.
- Play from disk reads the whole sound from the file when it starts,
  rather than a buffer at a time through the program's buffer.
- The Apple Sound Chip is macrt's own: where it is, the two queues and
  what the speaker takes from them are what Digital Messiah needs, not
  taken from Apple's description of the chip. What a program writes to
  the rest of it, from $800, is kept and reads back, but isn't heard: a
  volume or a way of playing it sets there makes no difference.


## What happens at launch

1. **Memory.** macrt reads the application's `SIZE` resource (or, without
   one, the sizes from the Finder's Get Info) and gives it a partition of
   that size in an 8 MB Mac. `--memory` gives it a size of your own. An application that asks for more than is
   free is refused, and macrt says how much it needs.
2. **The A5 world.** `CODE 0` describes the application's globals, which
   sit below A5, and the jump table, which sits above it. macrt builds them
   as the Segment Loader did and loads `CODE 1`. The other segments load
   when the code first calls into them.
3. **The processor.** unicorn's 68020, in 24-bit mode, starts at the
   first jump-table entry. Gestalt, `SysEnvirons` and the low-memory
   globals say it's a Mac Plus, with a 68000 and no floating-point unit,
   and the exception frames it stacks are a 68000's (see `--model`).
   The few instructions of a 68020 and a 68881 that unicorn doesn't run
   (`CHK2` and `CMP2`, packed decimal `FMOVE`, an `FMOVE` of immediate
   data to the floating-point control registers, `FSAVE` and `FRESTORE`)
   stop it, and macrt runs them in Python (`macrt/m68k/instructions.py`).
4. **Traps.** Every A-line trap the code executes (`_NewWindow`,
   `_DrawString`, `_WaitNextEvent` and so on) stops the processor. The
   matching Python routine then reads its arguments from the 68k stack or
   registers and does what Inside Macintosh says that routine does.
   - Windows and menus become Qt windows and menus.
   - QuickDraw draws into a 1-bit bitmap for each window, which Qt shows.
   - The Mac's data structures (window records, handles, regions and so
     on) are real, in the Mac's memory, so code that reads them directly
     still works.
5. **Events.** Mouse clicks, keys, and update and activate events come from
   Qt and are queued for `GetNextEvent` and `WaitNextEvent`. An application
   waiting in `WaitNextEvent` lets the others run. One whose `SIZE`
   resource says it takes high-level events finds an Open Application
   Apple event waiting, as System 7's Finder sends when it opens an
   application without documents.


## What works

There are more than 700 Toolbox and Operating System routines:

- **Memory Manager:** handles, pointers, heap zones, purging, the system
  heap, and MultiFinder's temporary memory, from a zone of its own above
  the applications' partitions. A block that grows, with
  `SetPtrSize` or `SetHandleSize`, grows where it is when the relocatable
  blocks after it can be moved or purged out of the way, and blocks are a
  multiple of 2 bytes long on a 68000 and of 4 on later processors, as
  the ROM makes them. `MoveHHi` moves a block up to the first block above
  it that can't move, and `ResrvMem` makes room low in the zone, moving
  handles up out of the way, so that a block a program keeps locked
  doesn't split the room it needs for the large ones it allocates next,
  as Stratego's offscreen pixel maps need.
- **Segment Loader:** `LoadSeg`, `UnloadSeg` (given an address in the
  segment or one of its jump-table entries, as Pascal's `@` gives; an
  entry may be called through an address with flags in its top byte,
  which a 68000 ignores),
  `GetAppParms`, `ExitToShell` and `_Launch`.
- **Resource Manager:** the resource chain, from the application down to
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
  System file](#a-real-system-file)), and `SizeResource` gives their
  size expanded. A resource read in goes in the system heap if its
  `resSysHeap` attribute says so, and otherwise in the current zone when
  that's the system heap or one the program made with `InitZone`, as an
  `INIT` sets it to keep what it reads; else in the heap of the
  application whose file it's from.
- **QuickDraw**, in black and white:
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
- **Font Manager:** font names and numbers (`GetFontName`, `GetFNum`),
  `RealFont`, `SetFractEnable` and `SetFScaleDisable`, and `FMSwapFont`,
  which picks the bitmap font or your computer's font for a request,
  fills in its output record and leaves the global width table for it in
  the system heap, where `WidthTabHandle`, `WidthPtr` and `WidthListHand`
  find it (Inside Macintosh IV, the Font Manager): each character's
  width as QuickDraw draws it, Microsoft Word 4 adding up its lines from
  them. `FontMetrics` gives `GetFontInfo`'s measures in fixed point, and
  the table's handle. There are no outline fonts (`IsOutline`);
- **Colour windows:** `NewCWindow` and `GetNewCWindow` make a window
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
- **Palette Manager:** a colour window's palette (`NewPalette`,
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
- **Color Picker Package** (`Pack12`): colours converted between RGB,
  CMY, HSL and HSV (`RGB2HSV` and the rest, `Fix2SmallFract` and
  `SmallFract2Fix`), and `GetColor`, which asks with your computer's own
  colour dialog, the program's prompt as its title. The dialog keeps 8
  bits of each component, so a colour changed in it comes back to that
  precision.
- **Window Manager:** the standard window kinds, with dragging, growing,
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
- **Menu Manager:** `MENU` and `MBAR` resources, key equivalents, marks,
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
- **Help Manager:** System 7's Help menu. `HMGetHelpMenuHandle` gives an
  application its own copy of it, with About Balloon Help and Show
  Balloons, for it to append its items to (Inside Macintosh: More
  Macintosh Toolbox, 3-83). Once it has, the menu's balloon is at the
  right of the bar, and `MenuSelect` and `MenuKey` return
  `kHMHelpMenuID` (-16490) with one of its items. Balloons aren't shown:
  `HMGetBalloons` is false, as with Show Balloons off, and the two
  standard items are dimmed. `HMShowBalloon` and `HMShowMenuBalloon` say
  help is off (`hmHelpDisabled`); the balloons' font and size, and the
  `hdlg` and `hmnu` resource IDs an application sets, it gets back.
- **Event Manager:** `GetNextEvent`, `WaitNextEvent`, `EventAvail`,
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
- **Control Manager:** buttons, check boxes, radio buttons and scroll bars,
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
- **Dialog Manager:** modal and modeless dialogs, alerts, `ParamText`,
  filter procedures and the item calls, with edit fields edited through
  TextEdit. On a colour machine a `GetNewDialog` dialog is a colour
  window when there's a `dctb` of its ID, and an alert when there's an
  `actb`, in that table's colours, as `NewColorDialog`'s are. Without one
  it's an old grafPort, as Inside Macintosh V says, which programs that
  draw straight into a dialog's `portBits` count on (Pinball Arcade).
  `NewDialog`'s are black-and-white ones.
- **List Manager:** lists drawn by `LDEF` 0 or the application's own
  `LDEF`, with clicks, Shift and Command to extend the selection,
  dragging, autoscrolling, scroll bars and double clicks. Cells are kept
  where the ROM keeps them, so code that reads a list's record and its
  data directly sees what it expects.
- **TextEdit:** editing, selection, line breaking, scrolling, styled text
  and `TETextBox`; and the routine at `TEDoText`, for programs that find,
  highlight, draw and place the caret through it themselves. A record's
  `highHook` and `caretHook` are called as TextEdit's own, `_InvertRect`,
  is: the rectangle's address on the stack, for the hook to pop.
- **Scrap Manager:** the desk scrap. Text in it is shared with your
  computer's clipboard, both ways. `UnloadScrap` writes it to the
  Clipboard File in the System Folder, as a Mac does.
- **File Manager:** files, folders and volumes, the HFS catalog calls,
  working directories, the `FSSpec` calls and `FindFolder`. See
  [Documents and saving](#documents-and-saving).
- **Device Manager:** an application's own drivers, the `DRVR` resources
  in its file. `Open` finds one by name and puts it in the unit table, and
  `Read`, `Write`, `Control`, `Status`, `KillIO` and `Close` call its
  routines, synchronously, asynchronously or immediately; the driver
  finishes each request through `IODone`, which calls the request's
  completion routine. `Open` finds the System file's drivers too, from
  `--system` or the disk's System (see [A real System
  file](#a-real-system-file)), except where macrt has its own: the Sound
  Driver, `.Print` and `.Sony` (see [Games from 1984](#games-from-1984)),
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
- **Desk Manager:** desk accessories, the `DRVR`s an application lists
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
- **Alias Manager:** alias records in System 7's format, found again
  after their file or folder has been moved or renamed, and brought up to
  date; `MatchAlias` and `GetAliasInfo`; `ResolveAliasFile`, which follows
  the Finder's alias files; and Apple event coercions between an alias
  and an `FSSpec`. There are no file servers, so an alias whose disk
  isn't there doesn't resolve.
- **Standard File:** the Open and Save dialogs, filtered by file type and
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
- **Icons:** `ICON`, `SICN`, `cicn` and icon families, through the mask; a
  `cicn` in its colours when the screen has more than 2 bits a pixel.
  `ForEachIconDo` calls a program's icon action function for each type
  of icon its selector names, and keeps what the function leaves in the
  suite.
- **Process Manager and MultiFinder:** the process calls, temporary memory
  and `SetFrontProcess`.
- **Apple Event Manager:** descriptors, lists, records, and Apple events
  with their parameters and attributes; the handler tables, object
  accessors and object callbacks, kept though nothing resolves object
  specifiers; and coercions between numbers, text and four-character
  codes, plus the application's own coercion handlers. An application gets the Open
  Application event at launch (see [What happens at
  launch](#what-happens-at-launch)), can look through what's waiting with
  `GetSpecificHighLevelEvent`, and can send events to itself, which is
  how recordable applications carry out their own commands.
- **Edition Manager:** publishers and subscribers, registered across all
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
- **Component Manager:** components registered from a `thng` resource
  or by the program, found by their description, opened, called and
  closed, with their own storage and A5 world, captured and delegated to.
  The Sound control panel's sub-panels are components, in its own file.
- **Communications Toolbox utilities:** `AppendDITL`, `CountDITL` and
  `ShortenDITL`, which add items to a dialog and take them away again, as
  the Sound control panel does for each sub-panel. The rest of the
  Communications Toolbox isn't there.
- **PPC Toolbox:** `PPCInit`, and ports opened and closed, as System 7's
  applications do at startup, though nothing can connect to them. The
  Process Manager names each application's own port. `Gestalt`'s `ppc `
  says the toolbox is there and initialised, with no network, and `os  `
  that `LaunchApplication` takes an `FSSpec` and can launch an
  application without quitting.
- **SANE:** `FP68K`'s arithmetic, comparisons, conversions and
  environment calls, correctly rounded in every rounding direction and
  precision, with the Apple Numerics Manual's exceptions, NaN codes and
  halts; `Elems68K`'s logarithms, exponentials, powers, financial
  functions, trigonometry and random numbers; and `PStr2Dec`, `CStr2Dec`
  and `Dec2Str`.
- **International Utilities:** dates and times written out as the `INTL`
  resources say, `IUMetric`, `IUGetIntl`, `IUSetIntl`, and string
  comparison and equality.
- **Script Manager:** the Roman script only. Character types, upper and
  lower case and accents (`Transliterate`, `UppercaseText` and the like),
  words (`FindWord`), line breaks (`StyledLineBreak`), `TruncString`,
  justified text (`MeasureJust`, `DrawJust`, `Pixel2Char`), and the
  Script Manager's variables.
- **Other managers:** Gestalt, `SysEnvirons`, the Notification Manager
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
- **The hardware**, for programs from the Mac's first years: the screen
  buffer at `ScrnBase`, the VIA, and the Event Manager's low-memory
  record of the mouse and keyboard (see [Games from
  1984](#games-from-1984)).
- **Printing Manager:** the calls of System 6 and 7's `PrGlue`, and the
  printer resource file and `.Print` driver that earlier applications
  call through, printing to a PDF (see [Printing](#printing)). `PrGeneral`
  answers that it can't do what's asked of it, as a printer without those
  features does.
- **Sound:** the Sound Driver's square-wave, four-tone and free-form
  sounds, and samples a program puts in the Mac Plus sound buffer, played
  through your computer's sound output (see [Sound](#sound)). The Sound
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

Not yet:

- Apple events and PPC sessions between applications;
- anything plugged into the serial ports, and AppleTalk;
- in custom Open and Save dialogs, the application's event filter and
  System 7's activation procedures.

An application that calls these gets on as far as it can without them (see
below).


## When it stops

### A call macrt doesn't implement

```
macrt: MyApp: SetDeskCPat (trap $AA47) isn't implemented; skipped
```

The routine is known but has nothing behind it yet: here `SetDeskCPat`,
which sets a colour desktop pattern. A routine that comes through a
package or dispatch trap (`Pack3`, `QDExtensions` and the rest) is named by the
routine its selector picks rather than the trap. macrt takes its
arguments off the stack and returns 0, or `unimpErr` (-4) for a routine
that returns an error code. Many applications carry on regardless, so each
missing call is reported only once. When the application quits, macrt
counts them up:

```
macrt: MyApp called traps macrt doesn't implement: SetDeskCPat (1), HMGetHelpMenuHandle (1)
```

That list is the most useful thing to report: it says exactly what an
application is waiting for.

### A system error

When the application does something it can't recover from, macrt stops it
and shows the classic system error alert. The other applications keep
running. The terminal gets the details:

```
macrt: MyApp stopped: system error 3 (illegal instruction): at $00002A
  PC 0000002A  SR 2000
  D0-D7 00000000 0000000C 00000000 00000000 00000000 00000000 00000000 00000000
  A0-A7 00000000 00084A10 00000000 00000000 00000000 001840F8 0017FE40 0017FE2C
  last traps: GetNextEvent at $08F2A4, …, Get1Resource at $0899C2, HLock at $0899CA
```

The first line says what went wrong. Here, MyApp jumped to $00002A, in
low memory, which isn't code (see the table below). Below it are the
registers and the last 16 traps, newest last, with the address each was
called from.

When the first line only names an exception, the last traps usually show
the cause. Often a call shortly before was skipped, and the application
went on with a value that call should have filled in.

| ID | Name | What it usually means here |
| --- | --- | --- |
| 0 | macrt itself failed | A bug in macrt, not in the application. A Python traceback comes with it. |
| 1 | bus error | The application read or wrote memory outside the Mac's 8 MB, or passed a bad pointer to a trap. Usually it's a handle from a call that failed earlier. |
| 2 | address error | It jumped to an odd address. |
| 3 | illegal instruction | It ran into data: often a call through a NIL procedure pointer, or a segment that isn't code. |
| 4 | zero divide | It divided by zero, often by a value a skipped call should have set. |
| 5 | check trap | A `CHK` instruction failed (Pascal range checking). |
| 6 | overflow trap | A `TRAPV` instruction failed. |
| 7 | privilege violation | It ran an instruction that isn't allowed. |
| 8 | trace trap | The trace bit was set. |
| 10 | line 1111 trap | An F-line instruction that the 68020 and its 68881 don't have, such as an MMU instruction. Floating-point instructions themselves work, whichever `--model` it is. |
| 11 | miscellaneous exception | Any other processor exception. |
| 12 | unimplemented trap | A trap macrt doesn't even know the name of, or a private call. PrintMonitor's private MultiFinder calls stop it here. |
| 15 | segment loader error | A `CODE` segment that's missing or compressed, or one built for the far code model that the application's own runtime doesn't load. |
| 25 | out of memory | A Toolbox call couldn't get the memory it had to have. Most calls report `memFullErr` instead and let the application decide. |

### Looking closer

- `--trace-traps` logs every trap as it's called, with the address it was
  called from. Use it to see what an application was doing before it
  stopped, or why it's sitting still. A package call is logged with the
  routine it's for, by Apple's name:

  ```
  macrt: Fly Swatter: FP68K FMULS at $1033F6
  macrt: Microsoft Excel: IUMagString at $1193A6
  ```
- `--view` shows the application's menus, windows and dialogs from its
  resources without running any code. If you mainly want to see what an
  application looked like, this always works.
- `--list` shows what the application is made of. An `ALRT` or `STR#`
  near the error often says what the application was trying to tell you.


## Writing a test application

`tests/apps` holds small 68k applications written in assembly, one per
part of the Toolbox: Hello (windows and menus), Controls, Dialogs, Edit
(TextEdit and the scrap), Lists (the List Manager), Menus (its own
`MBDF`), Frames (its own `WDEF`) and Launcher (`_Launch`). To build them you need
binutils for m68k (`apt install binutils-m68k-linux-gnu`). Then run:

```sh
python tests/apps/build.py
```

That assembles each `.s` file and wraps the code, with the resources it
needs, into a MacBinary file next to it. The built `.bin` files are checked
in, so the tests don't need the assembler. `tests/apps/traps.inc` defines
the trap words. Each application is one code segment, and the end of
`build.py` lists the resources each one gets. To try one, run it like any
other application:

```sh
python -m macrt tests/apps/Dialogs.bin --trace-traps
```

Keep what you need in registers the way Inside Macintosh's "Using
Assembly Language" says: a Toolbox routine called through the stack keeps
only A2-A6 and D3-D7, and in macrt one that has no result leaves 0 in D0.
