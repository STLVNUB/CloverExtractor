import sys, os, shutil, time
sys.path.append(os.path.abspath(os.path.dirname(os.path.realpath(__file__))))
import run, reveal

class CloverBuild:

    '''
    Module that builds the Clover bootloader - or rather attempts to.
    Build structure and functions credit to Dids and his clover-builder:

    https://github.com/Dids/clover-builder
    '''

    def __init__(self, **kwargs):
        # Setup the default path - and expand it
        self.source     = kwargs.get("source", "~/src")
        self.source     = os.path.abspath(os.path.expanduser(self.source))
        if not os.path.exists(self.source):
            os.mkdir(self.source)
        # Setup the UDK repo
        self.udk_repo   = kwargs.get("udk_repo", "https://github.com/tianocore/edk2")
        self.udk_branch = kwargs.get("udk_branch", "UDK2018")
        self.udk_path   = kwargs.get("udk_path", "UDK2018")
        self.udk_path   = os.path.join(self.source, self.udk_path)
        # Setup the Clover repo
        self.c_repo     = kwargs.get("clover_repo", "https://svn.code.sf.net/p/cloverefiboot/code")
        self.c_path     = kwargs.get("clover_path", "Clover")
        self.c_path     = os.path.join(self.udk_path, self.c_path)
        # Setup the out dir
        self.out        = os.path.join(self.c_path, "CloverPackage", "sym")
        # Setup the Clover EFI path
        self.ce_path    = os.path.join(self.c_path, "CloverPackage/CloverV2/drivers-Off")
        # Setup the efi drivers
        self.efi_drivers = kwargs.get("efi_drivers", [])
        if not len(self.efi_drivers):
            self.efi_drivers = [
                {
                    "repo" : "https://github.com/acidanthera/AptioFixPkg",
                    "path" : "AptioFixPkg", # Joined with source
                    "out"  : "AptioFixPkg/UDK/Build/AptioFixPkg/RELEASE_XCODE5/X64",
                    "name" : ["AptioMemoryFix.efi", "AptioInputFix.efi"],
                    "run"  : "macbuild.tool",
                    "lang" : "bash"
                },
                {
                    "repo" : "https://github.com/acidanthera/ApfsSupportPkg",
                    "path" : "ApfsSupportPkg", # Joined with source
                    "out"  : "ApfsSupportPkg/UDK/Build/ApfsSupportPkg/RELEASE_XCODE5/X64",
                    "name" : ["ApfsDriverLoader.efi"],
                    "run"  : "macbuild.tool",
                    "lang" : "bash"
                }
            ]
        # Setup the companion modules
        self.r          = run.Run()
        self.re         = reveal.Reveal()
        # Debug options
        self.debug      = kwargs.get("debug", False)

    def update_udk(self):
        # Updates UDK2018 - or clones it if it doesn't exist
        if not os.path.exists(os.path.join(self.udk_path, ".git")):
            # Clone!
            print("Checking out a shiny new copy of UDK2018...")
            out = self.r.run({"args":["git", "clone", self.udk_repo, "-b", self.udk_branch, "--depth", "1", self.udk_path], "stream":self.debug})
            if out[2] != 0:
                print("Failed to check out UDK2018!")
                return False
        # Already cloned once - just update
        print("Updating UDK2018...")
        cwd = os.getcwd()
        os.chdir(self.udk_path)
        out = self.r.run([
            {"args":["git", "pull"], "stream":self.debug},
            {"args":["git", "clean", "-fdx", "-e", "Clover/"], "stream":self.debug}
        ], True)
        os.chdir(cwd)
        if out[len(out)-1][2] != 0:
            print("Failed to update UDK2018!")
            return False
        return True

    def update_clover(self):
        # Updates Clover - or clones it if it doesn't exist
        if not os.path.exists(os.path.join(self.c_path, ".svn")):
            # Clone!
            print("Checking out a shiny new copy of Clover...")
            out = self.r.run({"args":["svn", "co", self.c_repo, self.c_path], "stream":self.debug})
            if out[2] != 0:
                print("Failed to check out Clover!")
                return False
        # Already cloned once - just update
        print("Updating Clover...")
        cwd = os.getcwd()
        os.chdir(self.udk_path)
        rev = self.get_clover_revision()
        if not rev:
            print("No Clover revision located!")
            return False
        out = self.r.run([
            # {"args":["svn", "up", "-r{}".format(rev)], "stream":self.debug},
            {"args":["svn", "up", "-rHEAD"], "stream":self.debug},
            {"args":["svn", "revert", "-R", "."], "stream":self.debug},
            {"args":["svn", "cleanup", "--remove-unversioned"], "stream":self.debug}
        ], True)
        os.chdir(cwd)
        if out[len(out)-1][2] != 0:
            print("Failed to update Clover!")
            return False
        return True

    def get_clover_revision(self):
        # Gets the revision from the Clover dir if exists - otherwise returns None
        if not os.path.exists(os.path.join(self.c_path, ".svn")):
            return None
        cwd = os.getcwd()
        os.chdir(self.c_path)
        out = self.r.run({"args":["svn", "info"]})[0]
        try:
            rev = out.lower().split("revision: ")[1].split("\n")[0]
        except:
            rev = ""
        if not len(rev):
            return None
        return rev

    def build_efi_drivers(self):
        output = []
        cwd = os.getcwd()
        print("Building EFI drivers...")
        for driver in self.efi_drivers:
            os.chdir(self.source)
            if not all(key in driver for key in ["repo", "path", "out", "name", "run", "lang"]):
                print("Driver missing info - skipping...")
                continue
            if not os.path.exists(os.path.join(self.source, driver["path"], ".git")):
                # Clone it
                print("Checking out a shiny new copy of {}".format(driver["path"]))
                out = self.r.run({"args":["git", "clone", driver["repo"]], "stream":self.debug})
                if out[2] != 0:
                    print("Error cloning!")
                    continue
            # cd
            os.chdir(driver["path"])
            # Check for updates
            self.r.run({"args":["git", "pull"], "stream":self.debug})
            # Chmod
            self.r.run({"args":["chmod", "+x", driver["run"]]})
            # Run it
            out = self.r.run({"args":[driver["lang"], driver["run"]], "stream":self.debug})
            if out[2] != 0:
                print("Failed to build {}!".format(driver["path"]))
                continue
            # Copy
            if type(driver["name"]) is str:
                driver["name"] = [driver["name"]]
            for d in driver["name"]:
                # Copy the drivers!
                try:
                    shutil.copy(os.path.join(self.source, driver["out"], d), os.path.join(self.ce_path, "drivers64", d))
                    shutil.copy(os.path.join(self.source, driver["out"], d), os.path.join(self.ce_path, "drivers64UEFI", d))
                except:
                    print("Failed to copy {}!".format(d))

    def build_clover(self):
        # Preliminary updates
        if not self.update_udk() or not self.update_clover():
            # Updates failed :(
            return False
        # Compile base tools
        print("Compiling base tools...")
        out = self.r.run({"args":["make", "-C", os.path.join(self.udk_path, "BaseTools", "Source", "C")], "stream":self.debug})
        if out[2] != 0:
            print("Failed to compile base tools!")
            return False
        # Setup UDK
        print("Setting up UDK...")
        cwd = os.getcwd()
        os.chdir(self.udk_path)
        out = self.r.run({"args":["bash", "-c", "source edksetup.sh"], "stream":self.debug})
        if out[2] != 0:
            print("Failed to setup UDK!")
            return False
        # Build gettext, mtoc, and nasm (if needed)
        os.chdir(self.c_path)
        if not os.path.exists(os.path.join(self.source, "opt", "local", "bin", "gettext")):
            out = self.r.run({"args":["bash", "buildgettext.sh"], "stream":self.debug})
            if out[2] != 0:
                print("Failed to build gettext!")
                return False
        if not os.path.exists(os.path.join(self.source, "opt", "local", "bin", "mtoc.NEW")):
            out = self.r.run({"args":["bash", "buildmtoc.sh"], "stream":self.debug})
            if out[2] != 0:
                print("Failed to build mtoc!")
                return False
        if not os.path.exists(os.path.join(self.source, "opt", "local", "bin", "nasm")):
            out = self.r.run({"args":["bash", "buildnasm.sh"], "stream":self.debug})
            if out[2] != 0:
                print("Failed to build nasm!")
                return False
        # Install UDK patches
        print("Installing UDK patches...")
        out = self.r.run({"args":"cp -R \"{}\"/Patches_for_UDK2018/* ../".format(self.c_path), "stream":self.debug, "shell":True})
        if out[2] != 0:
            print("Failed to install UDK patches!")
            return False
        print("Cleaning Clover...")
        out = self.r.run([
            {"args":["bash", "ebuild.sh", "-cleanall"], "stream":self.debug},
            {"args":["bash", "ebuild.sh", "-fr"], "stream":self.debug}
        ], True)
        if out[len(out)-1][2] != 0:
            print("Failed to clean Clover!")
            return False
        # Build the EFI drivers
        self.build_efi_drivers()
        # Download EFI drivers
        print("Downloading other EFI drivers...")
        for e in ["apfs.efi", "NTFS.efi", "HFSPlus_x64.efi"]:
            self.r.run({"args":"curl -sSLk https://github.com/Micky1979/Build_Clover/raw/work/Files/{} > \"{}\"/drivers64UEFI/{}".format(e, self.ce_path, e.replace("_x64", "")), "shell":True})
        # Copy over the other EFI drivers
        print("Copying other EFI drivers...")
        for e in ["apfs.efi", "NTFS.efi", "HFSPlus.efi"]:
            shutil.copy(os.path.join(self.ce_path, "drivers64UEFI", e), os.path.join(self.ce_path, "drivers64", e))
        print("Building Clover install package...")
        out = self.r.run({"args":["bash", "{}/CloverPackage/makepkg".format(self.c_path)], "stream":self.debug})
        if out[2] != 0:
            print("Failed to create Clover install package!")
            return False
        try:
            pack = out[0].split("Package name: [39;49;00m")[1].split("\n")[0].replace("\n", "").replace("\r", "")
        except:
            pack = None
        os.chdir(self.out)
        if pack != None and os.path.exists(pack):
            print("\nBuilt {}!\n".format(pack))
            return os.path.join(self.out, pack)
        return False