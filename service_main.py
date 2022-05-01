import service

def main():
    alertService = service.GeoTrackerAlertService()
    alertService.monitorAndAlert()

if __name__ == '__main__':
  main()
