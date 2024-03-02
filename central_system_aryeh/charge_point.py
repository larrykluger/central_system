from ocpp.v16 import ChargePoint as cp
from ocpp.routing import on
from ocpp.v16.enums import Action, RegistrationStatus
from ocpp.v16 import call_result, call
from datetime import datetime
from colorama import Fore
from colorama import Style
from datetime import timedelta


# Base class
# https://github.com/mobilityhouse/ocpp/blob/master/ocpp/charge_point.py

class ChargePoint(cp):
    def __init__(self, id, connection, response_timeout=30, log_level=0):
        self.log_level = log_level
        super().__init__(id, connection, response_timeout)

    # ===========================================================================
    # ===================== MESSAGES FROM THE CHARGE POINT ======================
    # ===========================================================================

    @on(Action.Authorize)
    def on_authorize_notification(self, id_tag):
        self.log(f"{Style.BRIGHT}{Fore.CYAN}Authorize{Style.RESET_ALL}")
        self.log(f"    id_tag: {id_tag}")
        return call_result.AuthorizePayload(
            id_tag_info={
                'expiry_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
                'parent_id_tag': "10",
                'status': RegistrationStatus.accepted}
        )

    @on(Action.BootNotification)
    def on_boot_notification(self, charge_point_vendor, charge_point_model, **kwargs):
        self.log(f"{Style.BRIGHT}{Fore.CYAN}Boot notification{Style.RESET_ALL}")
        self.log(f"    charge_point_vendor: {charge_point_vendor}")
        self.log(f"    charge_point_model: {charge_point_model}")
        self.log(f"    Kwargs: {kwargs}")
        return call_result.BootNotificationPayload(
            current_time=datetime.utcnow().isoformat(),
            interval=10,
            status=RegistrationStatus.accepted,
        )

    @on(Action.StatusNotification)
    def on_status_notification(self, connector_id, error_code, status, **kwargs):
        self.log(f"{Style.BRIGHT}{Fore.CYAN}Status notification{Style.RESET_ALL}")
        self.log(f"    connector_id: {connector_id}")
        self.log(f"    error_code: {error_code}")
        self.log(f"    status: {status}")
        self.log(f"    Kwargs: {kwargs}")
        return call_result.StatusNotificationPayload()

    @on(Action.Heartbeat)
    def on_heartbeat_notification(self, **kwargs):
        self.log(f"{Fore.RED}♥{Style.RESET_ALL}")
        return call_result.HeartbeatPayload(
            current_time=datetime.utcnow().isoformat()
        )

    @on(Action.StartTransaction)
    def on_start_transaction_notification(self, connector_id, id_tag, meter_start, timestamp, **kwargs):
        self.log(f"{Style.BRIGHT}{Fore.CYAN}Start Transaction{Style.RESET_ALL}")
        self.log(f"    connector_id: {connector_id}")
        self.log(f"    id_tag: {id_tag}")
        self.log(f"    meter_start: {meter_start}")
        self.log(f"    timestamp: {timestamp}")
        self.log(f"    Kwargs: {kwargs}")
        return call_result.StartTransactionPayload(
            id_tag_info={
                'expiry_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
                'parent_id_tag': "10",
                'status': RegistrationStatus.accepted},
            transaction_id=123
        )

    @on(Action.StopTransaction)
    def on_stop_transaction_notitication(self, meter_stop, timestamp, transaction_id, **kwargs):
        self.log(f"{Style.BRIGHT}{Fore.CYAN}Stop Transaction{Style.RESET_ALL}")
        self.log(f"    meter_stop: {meter_stop}")
        self.log(f"    timestamp: {timestamp}")
        self.log(f"    transaction_id: {transaction_id}")
        self.log(f"    Kwargs: {kwargs}")
        return call_result.StopTransactionPayload(
            id_tag_info={
                'expiry_date': (datetime.utcnow() + timedelta(days=1)).isoformat(),
                'parent_id_tag': "10",
                'status': RegistrationStatus.accepted},
        )

    # ===========================================================================
    # ===================== MESSAGES TO THE CHARGE POINT ========================
    # ===========================================================================

    async def change_configuration(self, key: str, value: str):
        """ OCPP 1.6 Section 5.3 Change Configuration 
            returns: ChangeConfigurationResponse.json
            https://github.com/mobilityhouse/ocpp/blob/master/ocpp/v16/schemas/ChangeConfigurationResponse.json
        """
        # https://github.com/mobilityhouse/ocpp/blob/master/ocpp/charge_point.py#L240
        return await self.call(call.ChangeConfigurationPayload(key=key, value=value))
    
    async def clear_cache(self):
        """ OCPP 1.6 Section 5.4 Clear Cache
            Clears the authorization cache 
            returns: ClearCacheResponse 
            https://github.com/mobilityhouse/ocpp/blob/master/ocpp/v16/schemas/ClearCacheResponse.json
        """
        return await self.call(call.ClearCachePayload())
    
    async def get_configuration(self):
        """ OCPP 1.6 Section 5.8 Get Configuration
            Get all of the configuration settings 
            returns: GetConfigurationResponse 
            https://github.com/mobilityhouse/ocpp/blob/master/ocpp/v16/schemas/GetConfigurationResponse.json
        """
        return await self.call(call.GetConfigurationPayload())


    # ===========================================================================
    # ============================== UTILITY METHODS ============================
    # ===========================================================================
    def log(self, msg):
        if self.log_level == 0:
            return
        print (msg)


