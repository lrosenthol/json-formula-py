import JsonFormula from "./json-formula.js";
import stringToNumber from "./stringToNumber.js";
import createForm from "./tutorial/Form.js";

function buildEngine(useStrictStringToNumber = true) {
  const debug = [];
  const jf = new JsonFormula({}, useStrictStringToNumber ? stringToNumber : null, debug);
  return { debug, jf, bootstrapped: false };
}

const engines = new Map();

function getEngine(useStrictStringToNumber = true) {
  const key = useStrictStringToNumber ? "strict" : "default";
  if (!engines.has(key)) {
    engines.set(key, buildEngine(useStrictStringToNumber));
  }
  return engines.get(key);
}

function normalize(value) {
  if (typeof value === "undefined") {
    return null;
  }
  return JSON.parse(JSON.stringify(value));
}

function bootstrapOfficialTestHelpers(engine) {
  if (engine.bootstrapped) {
    return;
  }
  engine.jf.search(
    `register("_summarize",
      &reduce(
        @,
        &merge(accumulated, fromEntries([[current, 1 + value(accumulated, current)]])),
        fromEntries(map(@, &[@, 0]))
      )
    )`,
    {},
  );
  engine.jf.search(
    `register(
      "_localDate",
      &split(@, "-") | datetime(@[0], @[1], @[2]))`,
    {},
  );
  engine.jf.search(
    'register("_product", &@[0] * @[1])',
    {},
  );
  engine.bootstrapped = true;
}

function execute(request) {
  const engine = getEngine(request.use_strict_string_to_number);
  engine.debug.length = 0;

  if (request.op === "bootstrap_official_test_helpers") {
    bootstrapOfficialTestHelpers(engine);
    return { status: "ok", result: null, debug: [...engine.debug] };
  }

  try {
    let result;
    if (request.op === "compile") {
      result = engine.jf.compile(request.expression, request.allowed_global_names || []);
    } else if (request.op === "run") {
      const data = request.fields_mode ? createForm(request.json_data) : request.json_data;
      result = engine.jf.run(request.ast, data, request.language || "en-US", request.globals || {});
    } else if (request.op === "search") {
      const data = request.fields_mode ? createForm(request.json_data) : request.json_data;
      result = engine.jf.search(
        request.expression,
        data,
        request.globals || {},
        request.language || "en-US",
      );
    } else if (request.op === "close") {
      process.exit(0);
    } else {
      return {
        status: "error",
        error_name: "EvaluationError",
        message: `Unsupported operation: ${request.op}`,
        debug: [...engine.debug],
      };
    }

    return {
      status: "ok",
      result: normalize(result),
      debug: [...engine.debug],
    };
  } catch (error) {
    return {
      status: "error",
      error_name: error?.name || "JsonFormulaError",
      message: error?.message || String(error),
      debug: [...engine.debug],
    };
  }
}

process.stdin.setEncoding("utf8");

let buffer = "";
process.stdin.on("data", (chunk) => {
  buffer += chunk;
  while (buffer.includes("\n")) {
    const newlineIndex = buffer.indexOf("\n");
    const line = buffer.slice(0, newlineIndex).trim();
    buffer = buffer.slice(newlineIndex + 1);
    if (!line) {
      continue;
    }
    const request = JSON.parse(line);
    const response = execute(request);
    process.stdout.write(`${JSON.stringify(response)}\n`);
  }
});
