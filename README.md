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

pyRevit Autosave is designed to be set once and largely forgotten about (until Revit crashes, of course). To enable the plugin, click the Autosave button on the toolbar. The dot should turn orange indicating the plugin is active. No further configuration is needed!

The plugin then runs in the background and will activate when switching between views to minimize interruption. A bar will appear at the top of the Revit window to indicate the document is saving. 

Note that undo history is lost after document saves: do not activate this tool if this is important to your workflows. 

If Revit crashes unexpectedly while working in a central model, either open the local model directly and sync, or open the model from the cloud and select Keep my changes and open the model when prompted. This tool does not replace the synchronize tool or native Revit sync.

If the autosave frequency is too frequent or infrequent, the Set Interval button can be used to adjust the frequency.

### Workshared and cloud models

Workshared and cloud models are excluded by default. To allow autosave for
them, add these options to the `[autosave]` section of the pyRevit user
configuration and restart/reload pyRevit:

```ini
include_workshared = true
include_cloud_models = true
```

Autosave calls `Document.Save()` on the active document and does not call
`SynchronizeWithCentral`; it is intended to save the local working copy only.
Use Revit's normal Sync command when you want to publish changes to the
central/cloud model. The diagnostic button reports eligibility but does not
run a save test.
