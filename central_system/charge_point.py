from ocpp.v16 import ChargePoint as cp
from ocpp.routing import on
from ocpp.v16.enums import Action, RegistrationStatus
from ocpp.v16 import call_result, call
from datetime import datetime


class ChargePoint(cp):
    @on(Action.BootNotification)
    def on_boot_notitication(self, charge_point_vendor, charge_point_model, **kwargs):
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )

    @on(Action.Heartbeat)
    def on_heartbeat_notification(
        self, **kwargs):
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )

    async def change_configuration(self, key: str, value: str):
        return await self.call(call.ChangeConfigurationPayload(key=key, value=value))

