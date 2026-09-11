"""Sweep XRpad detector gain x exposure time and trigger acquisitions (EPICS).

For each (gain, collection time) combination, sets the detector PVs over EPICS,
triggers an offset acquisition (data acquisition is currently commented out),
and blocks until the acquire status clears using a generator-based poll with a
timeout. Used to characterise detector behaviour across settings.

Requires a live beamline: a running EPICS IOC and the real detector. Included
as a code sample -- it does nothing off the beamline network.
"""

from epics import PV
from time import sleep

# PV definition
xrpad_collection_time = PV("SR10BM01XRPAD01:cam1:AcquireTime")
experiment_directory = PV("SR10BM01DETSEQIOC02:FILEPATH")
file_name = PV("SR10BM01DETSEQIOC02:FILENAME")
offset_acquire = PV("SR10BM01DETSEQIOC02:OFF_ACQ_PY")
data_acquire = PV("SR10BM01SSCAN5:scan2.EXSC")
data_collection_status = PV("SR10BM01XRPAD01:cam1:Acquire_RBV")
gain_setting = PV("SR10BM01XRPAD01:cam1:PEGain")
gain_RBV = PV("SR10BM01XRPAD01:cam1:PEGain_RBV")

# Sleep functions

def _sleep_or_abandon_sleep(
    i: int,
    max_time: int,
    wait_time: float,
    max_waiting_message: str,
    waiting_message: str = "Waiting",
):
    """Sleep for a short time, or else abandon sleep if plan is taking too long

    Parameters
    ----------
    i : int
        _description_
    max_time : int
        _description_
    wait_time : float
        _description_
    max_waiting_message : str
        _description_
    waiting_message : str
        _description_

    Returns
    -------
    _type_
        _description_

    Raises
    ------
    ValueError
        _description_
    """
    if i % (1 / wait_time) == 0:
        print(f"--{waiting_message}: {i*wait_time} seconds")
    if i > max_time / wait_time:
        raise ValueError(
            f"CRITICAL ERROR: Waited for {max_time} seconds, which is too long. "
            f"{max_waiting_message} Wait gets timed out."
        )
    return i, sleep(wait_time)

def wait_while_data_is_collecting(max_time: int = 75, wait_time: float = 0.01):
    print("Waiting for a data collection to finish")
    i = 0
    while int(data_collection_status.get()) == 1:  # 0: Done, 1: Acquiring
        sleep_generator = _sleep_or_abandon_sleep(
            i,
            max_time,
            wait_time,
            max_waiting_message=f"Data collection went on for {max_time} seconds, which is too long.",
            waiting_message="Waiting for data collection status is \"Acquiring\"",
        )
        yield from sleep_generator  # Now correctly yields sleep
        i += 1  # Increment i after sleeping

experiment_directory.put("/beamline/data/user/Setup/20250217")
file_name.put("offset_check")

gain_list = [2,3,4,5]
collection_time_list = [1,2,3,4,5,6,10,30,65]

gain_dict = {
    1:"0.5pF",
    2:"1pF",
    3:"2pF",
    4:"4pF",
    5:"8pF"    
}

i = len(gain_list)
j = len(collection_time_list)

for k, gain in enumerate(gain_list):
    print("--------------------------------------------")
    gain_setting.put(gain)
    sleep(2) # epics needs time to process. This adds overhead.
    print(f"Gain {k+1} out of {i}: {gain_dict[gain_RBV.get()]}")
    
    for l, collection_time in enumerate(collection_time_list):
    
        print("--------------------------------------------")
        print(f"Collection time {l+1} out of {j}: {collection_time} s")
        xrpad_collection_time.put(collection_time)
        sleep(0.01) # Wait for EPICS to accept changes
        
        # Collect offset
        offset_acquire.put(1)
        sleep(3) # It takes at least 2 s for the collectiong status to change following offset acquisition. This doesn't add overhead into the measurement.
        for _ in wait_while_data_is_collecting(): # Wait while data is collecting
            pass
        
        # # Collect data
        # data_acquire.put(1)
        # sleep(3) # It takes at least 2 s for the collectiong status to change following offset acquisition. This doesn't add overhead into the measurement. 
        # for _ in wait_while_data_is_collecting(): # Wait while data is collecting
        #     pass
        # sleep(3) # Wait for some epics sequence to finish. This adds overhead.

print("Data collection finishes")