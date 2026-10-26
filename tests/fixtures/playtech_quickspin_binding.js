// Structural reconstruction of the public command-binding path, not a game.
// Provenance is recorded in playtech_command_sources.json. No game is executed.
const playID = "quickspin.game.playMoney";
let currentGameMode = Glu6.Context.Default;
let currentBetType = "default";
function getCurrentGameMode() { return currentGameMode; }
function getCurrentBetType() { return currentBetType; }
function setCurrentBetType(betType) { currentBetType = betType; }
class DefaultPlayPolicy {
  play(info) {
    if (info.roundInProgress) {
      GLU.game.playOut(playID, { ID: 48775, parameters: null });
    } else {
      GLU.game.report.stake(info.roundCost);
      GLU.game.playMoney(playID, { ID: 40021, parameters: null }, info.featureType);
    }
  }
}
class GPASBridge {
  constructor() { this.playPolicies = new Map(); }
  bootstrap() {
    this.playPolicies.set(Glu6.Context.Default, new DefaultPlayPolicy());
  }
  async requestGameData() {
    return new Promise((resolve, reject) => {
      this.playPolicies.get(getCurrentGameMode()).play({
        roundInProgress: this.shouldContinueRound,
        roundCost: getRoundCost(),
        featureType: getCurrentBetType()
      });
    });
  }
  getAvailableFeatureConfig(featureName) {
    return getAvailableFeatureConfig(featureName);
  }
  setActivateFeature(featureOptions) {
    activateFeature(featureOptions);
    this.updateData(getCurrentGameMode());
    this.internalEventHandler.dispatchEvent(InternalGPASEvents.BET_MODE_UPDATED);
  }
}
let bridge;
function createPlatformBridge(type) {
  switch (type) {
    case "qs":
    case "gpas":
      bridge = new GPASBridge();
      break;
  }
}
function getPlatformBridgeHandle() { return bridge; }
async function bootstrap(options) {
  createPlatformBridge("gpas");
  const bridge2 = getPlatformBridgeHandle();
  bridge2.bootstrap();
}
const buyFeatureName = "buyFeature";
const extraBetName = "extraBet";
function getAvailableFeatureConfig(featureName) {
  let options;
  switch (featureName) {
    case buyFeatureName:
      options = getBuyFeatureOptions();
      break;
    case extraBetName:
      options = getExtraBetOptions();
      break;
    default:
      options = [];
      break;
  }
  return options;
}
function getBuyFeatureOptions() {
  const options = [];
  parseFeatureOptions();
  if (buyFeatureOptions.size > 0) {
    buyFeatureOptions.forEach((option) => {
      const cost = getRoundCostForBetType(option);
      const buyFeatureOption = { enabled: shouldOptionBeAllowed(option), cost };
      options.push(buyFeatureOption);
    });
  }
  return options;
}
function getExtraBetOptions() {
  const options = [];
  parseFeatureOptions();
  if (extraBetOptions.size > 0) {
    extraBetOptions.forEach((option) => {
      const cost = getRoundCostForBetType(option);
      const extraBetOption = { enabled: shouldOptionBeAllowed(option), cost };
      options.push(extraBetOption);
    });
  }
  return options;
}
function activateFeature(featureOptions) {
  if (!Array.isArray(featureOptions)) {
    featureOptions = [featureOptions];
  }
  let betType = getMatchingFeatureBetOption(featureOptions);
  setCurrentBetType(betType || "default");
}
function getMatchingFeatureBetOption(featureOptionsRequested) {
  const config = gameConfigs.get(getCurrentGameMode()).get("default");
  const availableOptions = config.game.activeBetOptions;
  let availableOptionFound = "";
  availableOptions.forEach((availableOption) => {
    let availableOptionString = availableOption;
    let numberOfMatchesFound = 0;
    featureOptionsRequested.forEach((requestedOption) => {
      const requestedOptionString = requestedOption.featureName + (requestedOption.option === 1 ? "" : requestedOption.option);
      let requestedOptionRegex = new RegExp(`${requestedOptionString}`, "i");
      if (availableOptionString.match(requestedOptionRegex)) {
        availableOptionString = availableOptionString.replace(requestedOptionRegex, "");
        numberOfMatchesFound++;
      }
    });
    if (availableOptionString === "" && numberOfMatchesFound === featureOptionsRequested.length) {
      availableOptionFound = availableOption;
    }
  });
  return availableOptionFound;
}
function parseFeatureOptions() {
  const config = gameConfigs.get(getCurrentGameMode()).get("default");
  const options = config.game.activeBetOptions;
  buyFeatureOptions = checkForFeature(buyFeatureName, options);
  extraBetOptions = checkForFeature(extraBetName, options);
}
function checkForFeature(featureName, betOptions) {
  const featureSet = new Set();
  let featureBaseString = featureName;
  if (betOptions.includes(featureBaseString)) {
    featureSet.add(featureBaseString);
    let hasMoreFeatures = true;
    let featureIndex = 2;
    while (hasMoreFeatures) {
      if (betOptions.includes(featureBaseString + featureIndex)) {
        featureSet.add(featureBaseString + featureIndex);
        featureIndex++;
      } else {
        hasMoreFeatures = false;
      }
    }
  }
  return featureSet;
}
bootstrap({});
