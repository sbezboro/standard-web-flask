from standardweb import celery
from standardweb.models import AccessLog


@celery.task()
def log(
        client_uuid, user_id, method, route, request_path, request_referrer,
        response_code, response_time, user_agent, ip_address
):
    log = AccessLog(
        client_uuid=client_uuid,
        user_id=user_id,
        method=method,
        route=route,
        request_path=request_path,
        request_referrer=request_referrer,
        response_code=response_code,
        response_time=response_time,
        user_agent=user_agent,
        ip_address=ip_address
    )

    log.save(commit=True)
