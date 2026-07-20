# FlashForge Adventurer 5 for Home Assistant

A custom Home Assistant integration for the FlashForge Adventurer 5 printer.

It adds multiple entities:

- machine state
- nozzle temperature
- bed temperature
- print head move mode
- current print job name
- current print job's progress
- camera feed

<img src="https://raw.githubusercontent.com/karmacop/hass-flashforge-adventurer-5/master/example.png" alt="Example dashboard" width="800"/>

## Installation

You can install it through [HACS](https://hacs.xyz/). Alternatively, you can
download this repo and add it to your `custom_components` directory.

After the integration is installed, go to Settings -> Devices & servies -> Integrations, and
configure it through the _Add integration_ button. If your printer is on it should be able to discover the IP address otherwise you will need to provide the
IP address of the printer. It might be a good idea to assign it a static IP address in your router settings.

## Printer compatibility

I own the Adventurer 5 printer at the moment, so that's the model which is 100%
supported. This has been forked from [https://github.com/modrzew/hass-flashforge-adventurer-3](https://github.com/modrzew/hass-flashforge-adventurer-3) so I'm not sure how far back these same commands work. Maybe it'll work with 3 and 4.
