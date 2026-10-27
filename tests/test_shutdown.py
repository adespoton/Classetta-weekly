"""The Shutdown Manager (Inside Macintosh V, The Shutdown Manager): the
procedures a program installs, each for the points it names, and removed
at all of them."""

from guest import Guest

sdOnPowerOff, sdOnRestart, sdOnUnmount = 1, 2, 4
PROC, OTHER = 0x00F00000, 0x00F00100


def test_a_procedure_is_kept_with_the_points_it_was_installed_for(qapp):
    g = Guest()
    g("ShutDwnInstall", PROC, sdOnPowerOff | sdOnRestart)
    g("ShutDwnInstall", PROC | 0xFF000000, sdOnUnmount)     # the same procedure
    g("ShutDwnInstall", OTHER, sdOnRestart)
    assert g.process.shutdown_procs == {PROC: sdOnPowerOff | sdOnRestart | sdOnUnmount,
                                        OTHER: sdOnRestart}


def test_removing_a_procedure_removes_it_at_every_point(qapp):
    g = Guest()
    g("ShutDwnInstall", PROC, sdOnPowerOff | sdOnUnmount)
    g("ShutDwnInstall", OTHER, sdOnRestart)
    g("ShutDwnRemove", PROC)
    g("ShutDwnRemove", 0x00F00200)                          # never installed
    assert g.process.shutdown_procs == {OTHER: sdOnRestart}
