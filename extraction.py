import json
import notehub_py
from notehub_py.models.get_project_events200_response import GetProjectEvents200Response
from notehub_py.rest import ApiException
from pprint import pprint

# Defining the host is optional and defaults to https://api.notefile.net
configuration = notehub_py.Configuration(
    host = "https://api.notefile.net"
)

# Configure Bearer authorization: personalAccessToken
configuration = notehub_py.Configuration(
    access_token = "api_key_HRr3Ao5P4u7ZyqyoHrZ1Ld2dzQ9MY7e/7DQ0OjjOPt0="
)

# Enter a context with an instance of the API client
with notehub_py.ApiClient(configuration) as api_client:
    # Create an instance of the API class
    api_instance = notehub_py.EventApi(api_client)
    project_or_product_uid = "edu.appstate.mathuesmr:capstone_pm_sensor" # str | 
    #page_size = 50 # int |  (optional) (default to 50)
    #page_num = 1 # int |  (optional) (default to 1)
    #device_uid = ["device_uid_example"] # List[str] | A Device UID. (optional)
    #sort_by = "captured" # str |  (optional) (default to "captured")
    #sort_order = "asc" # str |  (optional) (default to "asc")
    #start_date = 1628631763 # int | Unix timestamp (optional)
    #end_date = 1657894210 # int | Unix timestamp (optional)
    #date_type = "captured" # str | Which date to filter on, either 'captured' or 'uploaded'. This will apply to the startDate and endDate parameters (optional) (default to 'captured')
    #system_files_only = True # bool |  (optional)
    #files = "_health.qo, data.qo" # str |  (optional)
    format = "json" # str | Response format (JSON or CSV) (optional) (default to 'json')
    #serial_number = ["MikesSensor"] # List[str] | Filter by Serial Number (optional)
    #fleet_uid = ["My Fleet"] # List[str] | Filter by Fleet UID (optional)
    #session_uid = ["1163273f-193d-4620-a2d5-e7b092ba575e"] # List[str] | Filter by Session UID (optional)
    #event_uid = ["a921a5c0-2769-85e0-b000-2ecec6eb2531"] # List[str] | Filter by Event UID (optional)
    select_fields ="pm1p0,pm10p0" # str | Comma-separated list of fields to select from JSON payload (e.g., \"field1,field2.subfield,field3\"), this will reflect the columns in the CSV output. (optional)

    try:
        api_response = api_instance.get_project_events(project_or_product_uid, files = "data.qo")
        print("The response of EventApi->get_project_events:\n")
        for i in api_response.events:
         #   print(i)
            test = json.dumps(i.body)
            with open ("extraction_test.json", "w") as f:
                f.write(test)
            print(test)
        #pprint(api_response.events[1].body)
    except Exception as e:
        print("Exception when calling EventApi->get_project_events: %s\n" % e)
