// Postseal render of the actual numeric SVGs using the installed desktop runtime.
const fs = require('node:fs');
const path = require('node:path');
const crypto = require('node:crypto');
const assert = require('node:assert/strict');
const packageRoot = 'C:/Users/19430/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules';
const sharp = require(require.resolve('sharp', {paths: [packageRoot]}));
const read = file => JSON.parse(fs.readFileSync(file, 'utf8'));
const pin = file => ({path: file, bytes: fs.statSync(file).size,
  sha256: crypto.createHash('sha256').update(fs.readFileSync(file)).digest('hex')});
const here = __dirname;

async function main() {
  const seal = path.join(here, 'run/ALL_PREDICTIONS_SEALED.json');
  assert.equal(read(seal).status, 'ALL_PREDICTIONS_AND_ACCESS_SEALED');
  assert.equal(read(path.join(here, 'run/SCORE_PROVENANCE.json')).reference_opened_after_all_seals, true);
  assert.equal(read(path.join(here, 'visuals/SOURCES.json')).status, 'SCORED_NUMERIC_ONLY_NO_PRIVATE_PIXELS');
  const output = path.join(here, 'private/numeric_QA');
  fs.mkdirSync(output, {recursive: true});
  const files = [];
  for (const name of ['FULL_METRICS', 'DEPTH_INCREMENT', 'ALL_EVENTS']) {
    const source = path.join(here, 'visuals', name + '.svg');
    const destination = path.join(output, name + '.png');
    assert(!fs.existsSync(destination), 'Never overwrite a QA image');
    await sharp(fs.readFileSync(source)).png().toFile(destination);
    files.push({source: pin(source), output: pin(destination)});
    if (name === 'ALL_EVENTS') {
      const metadata = await sharp(destination).metadata();
      const height = Math.min(1200, metadata.height);
      for (const [suffix, top] of [['FIRST', 0], ['LAST', metadata.height - height]]) {
        const crop = path.join(output, name + '_' + suffix + '.png');
        assert(!fs.existsSync(crop));
        await sharp(destination).extract({left: 0, top, width: metadata.width, height}).png().toFile(crop);
        files.push({source: pin(source), output: pin(crop), rendered_numeric_crop: {top, height}});
      }
    }
  }
  const receipt = path.join(here, 'NUMERIC_VISUAL_RENDER.json');
  fs.writeFileSync(receipt, JSON.stringify({status: 'ACTUAL_SVG_RASTERIZED_AWAITING_LOCAL_VISUAL_INSPECTION',
    all_seal: pin(seal), helper: pin(__filename), node: pin(process.execPath), sharp: sharp.versions,
    files, source_RGB_pixels: false, source_depth_pixels: false, GT_rasters: false,
    new_model_http: 0, cost_usd: 0}, null, 2) + '\n', {flag: 'wx'});
  process.stdout.write('Actual numeric SVGs rasterized; local visual inspection remains required.\n');
}

main().catch(error => {process.stderr.write(String(error.stack) + '\n'); process.exitCode = 1;});
