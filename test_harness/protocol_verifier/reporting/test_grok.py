from pygrok import Grok
from typing import Optional, Tuple, Generator

pv_failure_grok = Grok(
    "%{TIMESTAMP_ISO8601:timestamp} -"
    r' {"eventList":\[%{GREEDYDATA:eventList}\],'
    '"jobId":"%{UUID:JobId}","jobName":"%{WORD:JobName}",'
    '"message":"%{DATA:FailureReason}","tag":"svdc_job_failed"}'
)

pv_success_grok = Grok(
    '{"jobId":"%{UUID:JobId}","jobName":"%{WORD:JobName}"'
    ',"message":"%{DATA:message}","tag":"svdc_job_success"}'
)

pv_aeordering_job_failed_grok = Grok(
    '%{TIMESTAMP_ISO8601:timestamp} - {"eventId":"%{DATA:eventId}","eventName"'
    ':"%{DATA:eventName}","jobId":"%{UUID:JobId}","jobName":"%{WORD:JobName}",'
    '"message":"%{DATA:FailureReason}","tag":"aeordering_job_failed"}'
)

pv_svdc_job_alarm_grok = Grok(
    "%{TIMESTAMP_ISO8601:timestamp} - "
    r'{"eventList":\[%{GREEDYDATA:eventList}\],'
    '"jobId":"%{UUID:JobId}","jobName":"%{WORD:JobName}",'
    '"message":"ALARM: %{DATA:Alarm}","tag":"svdc_job_alarm"}'
)


def parse_logfile(file_path: str) -> Generator[str, None, None]:
    with open(file_path, "r") as log:
        for line in log:
            yield line.strip()


def match_line(grok: Grok, line: str) -> Tuple[Optional[dict], bool]:
    match_grok = grok.match(line)
    if match_grok:
        return (match_grok, True)
    return (None, False)


if __name__ == "__main__":
    # file_path = "test_harness/protocol_verifier/reporting/smoke_test_1.log"
    file_path = "test_harness/protocol_verifier/reporting/unhappy_test.log"

    line_generator = parse_logfile(file_path)

    grok_dict = {
        pv_success_grok: [],
        pv_failure_grok: [],
        pv_aeordering_job_failed_grok: [],
        pv_svdc_job_alarm_grok: [],
    }
    for line in line_generator:
        for grok in grok_dict.keys():
            match_grok, success = match_line(grok, line)
            if success:
                grok_dict[grok].append(match_grok)
                break
    print("Finished analysing logs")
    print(
        f"pv_success_groks: {len(grok_dict[pv_success_grok])}\n"
        f"pv_failure_groks: {len(grok_dict[pv_failure_grok])}\n"
        f"pv_aeordering_job_failed_grok: "
        f"{len(grok_dict[pv_aeordering_job_failed_grok])}\n"
        f"pv_svdc_job_alarm_grok: {len(grok_dict[pv_svdc_job_alarm_grok])}\n"
    )
