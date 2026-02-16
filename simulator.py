from io import TextIOWrapper
import json
from dataclasses import dataclass
from pathlib import Path
import sys

from kernel import Kernel

MICRO_S = int
PID = int

NUM_MILIS_IN_SEC: MICRO_S = 1000
TIMER_INTERRUPT_INTERVAL: MICRO_S = 10

VALID_SCHEDULING_ALGORITHMS = {"FCFS", "Priority", "RR", "Multilevel"}
VALID_PROCESS_TYPES = {"Foreground", "Background"}

PROCESSES: str = "processes"
ARRIVAL: str = "arrival"
TOTAL_CPU_TIME: str = "total_cpu_time"
PRIORITY: str = "priority"
PRIORITY_CHANGES: str = "priority_change"
EVENT_ARRIVAL: str = "arrival"
NEW_PRIORITY: str = "new_priority"
PROCESS_TYPE: str = "type"

DEFAULT_PRIORITY = 32

class SimulationError(Exception):
    pass

@dataclass
class PriorityChangeEvent:
    arrival: MICRO_S
    new_priority: int

@dataclass
class Process:
    arrival: MICRO_S
    total_cpu_time: MICRO_S
    elapsed_cpu_time: MICRO_S
    priority: int
    priority_change_events: list[PriorityChangeEvent]
    process_type: str

class Simulator:
    elapsed_time: MICRO_S
    current_process: PID
    processes: dict[PID, Process]
    arrivals: list[Process]
    kernel: Kernel
    next_pid: PID
    simlog: TextIOWrapper
    needs_spacing: False
    process_0_runtime: MICRO_S
    student_logs: "StudentLogger"

    def __init__(self, emulation_description_path: Path, logfile_path: str, student_logs: bool):
        self.elapsed_time = 0
        self.current_process = 0
        self.processes = dict()
        self.arrivals = []
        self.next_pid = 1
        self.needs_spacing = False
        self.process_0_runtime = 0
        if student_logs:
            self.student_logs = StudentLogger(self)
        else:
            self.student_logs = StudentLogger(None)

        emulation_json = None
        with open(emulation_description_path, 'r') as file:
            emulation_json = json.load(file)

        assert(PROCESSES in emulation_json and type(emulation_json[PROCESSES]) is list)
        for process in emulation_json[PROCESSES]:
            assert(ARRIVAL in process and type(process[ARRIVAL]) is MICRO_S)
            assert(TOTAL_CPU_TIME in process and type(process[TOTAL_CPU_TIME]) is MICRO_S)
            
            priority = DEFAULT_PRIORITY
            if PRIORITY in process:
                assert(type(process[PRIORITY]) is int)
                priority = process[PRIORITY]

            priority_changes = []
            if PRIORITY_CHANGES in process:
                assert(type(process[PRIORITY_CHANGES]) is list)
                for change in process[PRIORITY_CHANGES]:
                    assert(EVENT_ARRIVAL in change and type(change[EVENT_ARRIVAL]) is int)
                    assert(NEW_PRIORITY in change and type(change[NEW_PRIORITY]) is int)
                    priority_changes.append(PriorityChangeEvent(change[EVENT_ARRIVAL], change[NEW_PRIORITY]))

            # Sort all event lists such that their last element is always the next event
            for event_list in [priority_changes]:
                event_list.sort(key=lambda c: c.arrival, reverse=True)

            process_type = "Foreground"
            if PROCESS_TYPE in process:
                assert(process[PROCESS_TYPE] in VALID_PROCESS_TYPES)
                process_type = process[PROCESS_TYPE]

            process = Process(process[ARRIVAL], process[TOTAL_CPU_TIME], 0, priority, priority_changes, process_type)
            assert_events_are_valid_and_not_at_same_time(process)
            self.arrivals.append(process)
        # Sort arrivals so earliest arrivals are at the end.
        self.arrivals.sort(key=lambda p: p.arrival, reverse=True)

        assert("scheduling_algorithm" in emulation_json and emulation_json["scheduling_algorithm"] in VALID_SCHEDULING_ALGORITHMS)
        self.simlog = open(logfile_path, 'w')
        self.kernel = Kernel(emulation_json["scheduling_algorithm"], self.student_logs)

    
    def run_simulator(self):
        # Emulation ends when all processes have finished.
        while len(self.processes) + len(self.arrivals) > 0:
            if self.current_process == 0:
                self.process_0_runtime += 1
            if self.process_0_runtime >= NUM_MILIS_IN_SEC:
                raise SimulationError( \
                """Process 0 (idle process) has been running for 1 second straight. 
                This will not happen in tested simulations and is likely a bug in the kernel.""")
            
            self.advance_current_process()

            self.check_for_arrival()

            if self.elapsed_time != 0 and self.elapsed_time % TIMER_INTERRUPT_INTERVAL == 0:
                self.switch_process(self.kernel.timer_interrupt())

            self.log_add_spacing()
            self.elapsed_time += 1
        self.simlog.close()

    def advance_current_process(self):
        if self.current_process == 0:
            return
        
        current_process = self.processes[self.current_process]
        current_process.elapsed_cpu_time += 1

        # If the current_process has finished execution
        if current_process.total_cpu_time <= current_process.elapsed_cpu_time:
            exiting_process = self.current_process
            self.log(f"Process {exiting_process} has finished execution and is exiting")
            new_process = self.kernel.syscall_exit()
            if new_process == exiting_process:
                raise SimulationError(f"Attempted to continue execution of exiting process (pid = {exiting_process})")
            
            del self.processes[exiting_process]
            
            self.switch_process(new_process)
            return


        event_list = current_process.priority_change_events
        while len(event_list) > 0 and event_list[len(event_list) - 1].arrival <= current_process.elapsed_cpu_time:
            priority_change = event_list.pop()
            self.log(f"Process {self.current_process} set priority to {priority_change.new_priority}")
            self.switch_process(self.kernel.syscall_set_priority(priority_change.new_priority))

    def check_for_arrival(self):
        while len(self.arrivals) > 0 and self.arrivals[len(self.arrivals) - 1].arrival == self.elapsed_time:
            new_process = self.arrivals.pop()
            self.processes[self.next_pid] = new_process
            self.log(f"{new_process.process_type} process {self.next_pid} arrived with priority {new_process.priority}")
            self.switch_process(self.kernel.new_process_arrived(self.next_pid, new_process.priority, new_process.process_type))
            self.next_pid += 1


    def switch_process(self, new_process: int):
        if new_process != 0:
            if new_process not in self.processes:
                raise SimulationError(f"Attempted to switch to unkown PID {new_process}")
            self.process_0_runtime = 0

        if new_process != self.current_process:
            self.log(f"Context switching to pid: {new_process}")
        self.current_process = new_process

    def log(self, str: str, student_log = False):
        if student_log:
            delimiter = '#'
        else:
            delimiter = ':'
        self.simlog.write(f"{self.elapsed_time / 1000:.3f}s {delimiter} {str}\n")
        self.needs_spacing = True
    
    def log_add_spacing(self):
        if self.needs_spacing:
            self.simlog.write("\n")
            self.needs_spacing = False

class StudentLogger:
    __simluator: Simulator

    def __init__(self, simulator: Simulator | None):
        self.__simluator = simulator

    def log(self, str: str):
        if self.__simluator is not None:
            self.__simluator.log(str, student_log=True)

# Having events at the same time as other events in the same process could cause a desync between what the simulator thinks is running and what the handler does.
# This assert ensures the process does not have this issue.
# Additionally ensures that all events will happen before the process exits.
def assert_events_are_valid_and_not_at_same_time(process: Process):
    event_arrivals = set()
    for event in process.priority_change_events:
        assert(event.arrival not in event_arrivals)
        event_arrivals.add(event.arrival)

    for event_arrival in event_arrivals:
        assert(event_arrival < process.total_cpu_time)

def print_usage():
    print("Usage: python simulator.py <simulation_description_path> <log_path> <optional --no-student-logs>")
    sys.exit(1)


if __name__ == "__main__":
    student_logs = True
    if len(sys.argv) <= 2 or len(sys.argv) >= 5:
        print_usage()
    if type(sys.argv[1]) is not str or type(sys.argv[2]) is not str:
        print_usage()
    if len(sys.argv) == 4:
        if sys.argv[3] != "--no-student-logs":
            print_usage()
        else:
            student_logs = False



    sim_description = Path(sys.argv[1])
    log_path = Path(sys.argv[2])
    simulator = Simulator(sim_description, log_path, student_logs)
    simulator.run_simulator()