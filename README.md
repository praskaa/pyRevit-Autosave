# pyRevit-Autosave
pyRevit-Autosave adds to Revit functionality that it should have had from day 1, saving time and sanity.

[![GitHub issues](https://img.shields.io/github/issues/alexdaversa/pyRevit-Autosave.svg?style=for-the-badge)](https://github.com/alexdaversa/pyRevit-Autosave/issues)
[![GitHub forks](https://img.shields.io/github/forks/alexdaversa/pyRevit-Autosave.svg?style=for-the-badge)](https://github.com/alexdaversa/pyRevit-Autosave/network)
[![GitHub stars](https://img.shields.io/github/stars/alexdaversa/pyRevit-Autosave.svg?style=for-the-badge&colorB=red)](https://github.com/alexdaversa/pyRevit-Autosave/stargazers)
[![License: GPL v3](https://img.shields.io/badge/License-GPL%20v3-blue.svg?style=for-the-badge)](http://www.gnu.org/licenses/gpl-3.0)
[![made with love in portland](https://img.shields.io/badge/%3C%2F%3E%20with%20%3C3-Philadelphia%2C%20PA-green.svg?style=for-the-badge)](https://en.wikipedia.org/wiki/Philadelphia)

## Installation
### pyRevit Extensions
This extension can be installed from the pyRevit extensions manager as of the latest WIP builds. The extension information can also be added to the extensions/extensions.json file for existing 4.x and 5.x installs.


### Manual Installation
Clone the repository to anywhere on your computer

In pyRevit, click Settings, expand the Custom Extension Directories section, and click Add Folder. The selected folder should have a folder inside named pyRevit-Autosave.extension.


## Usage

Click **AutoSave** in the ribbon to enable it for the current Revit session.
Click it again to disable it. Each new Revit session starts OFF.
When a document opens while AutoSave is OFF, pyRevit asks whether to enable
it for the current session. Choose **No** to leave it OFF.
Use **Set Interval** to change the saved interval preference.

| Ribbon status | Meaning |
| --- | --- |
| OFF | AutoSave is disabled. |
| ON - Starting | Waiting for Revit to run the background handler. |
| ON - Ready | The handler is running and the active document has no pending edits. |
| ON - Waiting | The handler is running and waiting for the interval or a chance to save. |
| ON - Saving | Revit is processing Save. |
| ON - Saved | Revit confirmed the local save. |
| ON - Skipped | The active document does not qualify for a local save. |
| ON - Error | The engine could not start, save failed, or Revit did not confirm the save. |

Hover over the AutoSave button or click **AutoSave Status** to see the
reason and the time of the last confirmed AutoSave for an eligible document.
Saving can clear Revit's undo history.

### Local save and worksharing

AutoSave saves an existing local file or a verified local copy of a
file-based workshared model. For cloud worksharing, it uses Revit's regular
Save command (Ctrl+S) to save the working copy to Revit's local cache.
Use **Synchronize with Central** manually to send changes to the shared model.

A central model opened directly, a cloud model without worksharing, a linked
or detached document, a read-only document, and a new document that needs
its first Save As are skipped.

Once the interval is due, AutoSave waits for a settled view change. If a
save remains overdue for 10 minutes, AutoSave can also run after 20 seconds
without mouse or keyboard input. These are the default timings.
