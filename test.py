class Test:

    def __init__(self):
        super().__init__()

    def test(self):

        print(__class__.__name__)



a  = Test()
a.test()