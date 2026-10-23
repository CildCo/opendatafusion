class Source:
    def read(self, cursor, limit):
        raise NotImplementedError


class Sink:
    def write(self, rows):
        raise NotImplementedError
