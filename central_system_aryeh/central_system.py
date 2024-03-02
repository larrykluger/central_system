"""
From https://github.com/mobilityhouse/ocpp/issues/86
"""

import logging
import asyncio
from charge_point import ChargePoint
from colorama import Fore
from colorama import Style

log_level = 1
def log(msg):
    if log_level == 0:
        return
    print (msg)

class CentralSystem:
    def __init__(self):
        self._chargers = {}

    def register_charger(self, cp: ChargePoint) -> asyncio.Queue:
        """ Register a new ChargePoint at the CSMS. The function returns a
        queue.  The CSMS will put a message on the queue if the CSMS wants to
        close the connection. 
        """
        queue = asyncio.Queue(maxsize=1)

        # Store a reference to the task so we can cancel it later if needed.
        task = asyncio.create_task(self.start_charger(cp, queue))
        # self._chargers[cp] is now a tuple!.
        # The [0] element is the charger obj
        # the [1] element is the queue obj
        self._chargers[cp] = task

        return queue

    async def start_charger(self, cp, queue):
        """ Start listening for message of charger. """
        try:
            await cp.start()
        except Exception as e:
            print(f"{Fore.RED}Charger {cp.id} disconnected: {e}{Style.RESET_ALL}")
        finally:
            # Make sure to remove reference to charger after it disconnected.
            del self._chargers[cp]

            # This will unblock the `on_connect()` handler and the connection
            # will be destroyed.
            await queue.put(True)

    ### FIX
    async def change_configuration(self, key: str, value: str):
        for cp in self._chargers:
            await cp.change_configuration(key, value)

    def disconnect_charger(self, id: str):
        for cp, task in self._chargers.items():
            if cp.id == id:
                task.cancel()
                return 
        raise ValueError(f"Charger {id} not connected.")
    
    async def get_configuration(self, id: str):
        for cp, task in self._chargers.items():
            if cp.id == id:
                return await cp.get_configuration()
        raise ValueError(f"Charger {id} not connected.")

