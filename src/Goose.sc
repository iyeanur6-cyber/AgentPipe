Goose {
	*honk {
		var play;
		play = {
			Mix.fill(74, {
				|i|
				var osc, env, freq, detune, pan;
				detune = rrand(-15.0, 15.0);
				freq = 350 + detune + (i * 0.2);
				osc = Saw.ar(freq) * Pulse.ar(freq * 0.5, 0.35);
				osc = BPF.ar(osc, XLine.kr(rrand(800, 1200), rrand(400, 600), 0.15), 0.3);
				env = EnvGen.ar(Env([0, 1, 0.6, 0], [0.01, 0.08, 0.12], [2, -2, -4]), doneAction: 2);
				pan = rrand(-0.8, 0.8);
				Pan2.ar(osc * env * 0.08, pan);
			});
		};
		^play.play;
	}

	*honkify {
		arg inputSignal;
		var fftSize, hopSize, windowType, chain, pitch, hasPitch, noise, synth;
		fftSize = 2048;
		hopSize = 0.25;
		windowType = 1;
		# pitch, hasPitch = Pitch.kr(inputSignal, initFreq: 440, minFreq: 60, maxFreq: 2000, ampThreshold: 0.02);
		chain = FFT(LocalBuf(fftSize), inputSignal, hopSize, windowType);
		chain = PV_MagSmudge(chain, 1.2);
		chain = PV_BrickWall(chain, 0.85);
		noise = WhiteNoise.ar(0.03) * LPF.ar(Dust.ar(800), pitch * 1.5);
		synth = IFFT(chain) * 0.7;
		synth = synth + noise;
		synth = BPF.ar(synth, pitch * 2.5, 0.4) * hasPitch;
		^synth;
	}
}
