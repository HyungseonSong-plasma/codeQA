import os
from pkg import helper as assist

class Worker(Base):
    def execute(self):
        assist()
        self.trace()

async def job():
    return run_external()
