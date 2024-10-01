from abc import ABC, abstractmethod


class GridBase(ABC):
    def __init__(self):
        super().__init__()

    @abstractmethod
    def stop_and_wait_threads(self):
        pass

    @abstractmethod
    def stop_threads(self):
        pass