class JazzGoblin:
    music: bool
    rhythm: bool
    my_man: bool

    def __init__(self, music: bool = False, rhythm: bool = False, my_man: bool = False):
        self.music = music
        self.rhythm = rhythm
        self.my_man = my_man

    def ask_for_more(self):
        if self.music and self.rhythm and self.my_man:
            print("who could ask for anything more?")
        else:
            print("I could ask for more, yeah.")

    def feed(self, food: Optional[bool] = False):
        if food:
            print("nom nom nom")
            self.ask_for_more()
        else:
            # you heartless fuck
            print("> : (")

    def skiddily_bop_bop_ba_woo_sham_boo(self):
        print("skilly skolly stittility skap skap skribbidi boo daaaaaa~~~")
        print("heyo lamo heyo lamo _eyo lamo eyo lamo_ HEYO LAMO HEYO LAMO")
        print("diddili iddiliy skree bam boo, baby, darling, I love you")
        self.trumpet_solo()

    def trumpet_solo(self, trumpet: Optional[bool]):
        if trumpet:
            if self.music:
                if self.rhythm:
                    print("braaaa braaAAAAAAA BAAAAAAAAAAWWWWOOOOOOOOOHHHHHHHHAAAAAAAAW")
                    return
        print("nfffffcvfffffff")
