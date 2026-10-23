(function () {
    var loadScripts = function (scripts, index, callback) {
        if (index < scripts.length) {
            var el = document.createElement('script');
            el.async = scripts[index].async;
            el.src = scripts[index].src;
            document.body.appendChild(el);
            el.addEventListener('load', function () {
                loadScripts(scripts, index + 1, callback);
            }, false);
            el.addEventListener('error', function () {
                loadScripts(scripts, index + 1, callback);
            }, false);
        } else if (callback) {
            callback();
        }
    };

    var launchParams = {
        gameBaseURL: './',
        provider: 'yggdrasil',
        demo: true
    };

    var splash = document.getElementById('splash');
    var logoContainer = document.createElement("div");
    logoContainer.id = "logo-container";

    var scripts = [];

    scripts.push({
         src: launchParams.gameBaseURL + 'engine-wrapper/' + launchParams.provider + '/engine.mjzkztc2.js',
         async: false
    });

    //scripts.push({
    //    src: 'http://localhost:4000/engine.mjzkztc2.js',
    //    async: false
    //});

    scripts.push({
        src: launchParams.gameBaseURL + 'engine-wrapper/' + launchParams.provider + '/engine-extensions.mjzkztc2.js',
        async: false
    });

    //scripts.push({
    //     src: 'http://localhost:4001/engine-extensions.mjzkztc2.js',
    //     async: false
    //});

    var scripts = scripts.concat([
        {src: launchParams.gameBaseURL + 'src/settings.11236.js', async: false},
        {src: launchParams.gameBaseURL + 'launcher.mjzkztc2.js', async: false},
        {src: launchParams.gameBaseURL + 'cocos2d-js-min.8ca23.js', async: true}
    ]);

    var engineLoaded = function () {
        window.PSGames.boot(launchParams, 'game');
    }

    loadScripts(scripts, 0, engineLoaded);

})();