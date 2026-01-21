import { Page, Locator, Frame } from "@playwright/test";
import { randomUUID } from "crypto";
import { RunnableFunctionWithParse } from "openai/lib/RunnableFunction";
import { z } from "zod";
import { getSanitizeOptions } from "./sanitizeHtml";

export const createActions = (
  page: Page,
): Record<string, RunnableFunctionWithParse<any>> => {
  // ----------------------------
  // Helpers (CSS selector + frames + shadowroot)
  // ----------------------------
  const normalizeSelector = (selector: string) => {
    return selector.trim().replace(/^css[=:]\s*/i, "");
  };

  const findLocatorAcrossFrames = async (cssSelector: string): Promise<Locator> => {
    const sel = normalizeSelector(cssSelector);

    // 1) Main document
    const main = page.locator(sel).first();
    if ((await main.count()) > 0) return main;

    // 2) Any iframe (includes nested)
    for (const frame of page.frames()) {
      if (frame === page.mainFrame()) continue;
      const loc = frame.locator(sel).first();
      if ((await loc.count()) > 0) return loc;
    }

    throw new Error(`Nenhum elemento encontrado (main/iframes) para o selector: ${cssSelector}`);
  };

  const waitVisibleEnabled = async (locator: Locator, timeoutMs = 15000) => {
    const start = Date.now();
    while (Date.now() - start < timeoutMs) {
      try {
        if ((await locator.isVisible()) && (await locator.isEnabled())) return;
      } catch {}
      await new Promise((r) => setTimeout(r, 250));
    }
    throw new Error("Elemento encontrado, porém permaneceu invisível ou desabilitado dentro do tempo limite.");
  };

  const waitOverlaysToDisappear = async () => {
    // Não falha se não existir
    try {
      await page
        .locator("app-alert-loading-box, .loading, .spinner, .overlay, [aria-busy='true']")
        .first()
        .waitFor({ state: "detached", timeout: 8000 });
    } catch {}
  };

  const robustClick = async (locator: Locator) => {
    await locator.waitFor({ state: "attached", timeout: 15000 });
    await waitOverlaysToDisappear();

    try {
      await locator.scrollIntoViewIfNeeded();
    } catch {}

    await waitVisibleEnabled(locator, 15000);

    // 1) normal
    try {
      await locator.click({ timeout: 10000 });
      return;
    } catch {}

    // 2) trial + click
    try {
      await locator.click({ trial: true, timeout: 3000 });
      await locator.click({ timeout: 10000 });
      return;
    } catch {}

    // 3) force (overlay/efeitos interceptando)
    await locator.click({ force: true, timeout: 10000 });
  };

  const robustFill = async (locator: Locator, value: string) => {
    await locator.waitFor({ state: "attached", timeout: 15000 });
    await waitOverlaysToDisappear();

    try {
      await locator.scrollIntoViewIfNeeded();
    } catch {}

    await waitVisibleEnabled(locator, 15000);

    // fill já lida bem com foco/seleção, mas mantemos robustez
    await locator.fill(value, { timeout: 10000 });
  };

  // Agora "getLocator" recebe SEMPRE um CSS selector
  const getLocator = async (cssSelector: string) => {
    return await findLocatorAcrossFrames(cssSelector);
  };

  // Quando geramos IDs, retornamos um CSS selector estável
  const createMarkedSelector = (id: string) => `[data-element-id="${id}"]`;

  return {
    locator_pressKey: {
      function: async (args: { elementId: string; key: string }) => {
        const { elementId, key } = args;
        const locator = await getLocator(elementId);
        await locator.press(key);
        return { success: true };
      },
      name: "locator_pressKey",
      description: "Presses a key while focused on the specified element.",
      parse: (args: string) => {
        return z.object({ elementId: z.string(), key: z.string() }).parse(JSON.parse(args));
      },
      parameters: {
        type: "object",
        properties: {
          elementId: { type: "string", description: "CSS selector (Playwright/CSS) for the element." },
          key: {
            type: "string",
            description: "The name of the key to press, e.g., 'Enter', 'ArrowUp', 'a'.",
          },
        },
      },
    },

    page_pressKey: {
      function: async (args: { key: string }) => {
        await page.keyboard.press(args.key);
        return { success: true };
      },
      name: "page_pressKey",
      description: "Presses a key globally on the page.",
      parse: (args: string) => z.object({ key: z.string() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          key: {
            type: "string",
            description: "The name of the key to press, e.g., 'Enter', 'ArrowDown', 'b'.",
          },
        },
      },
    },

    locateElement: {
      function: async (args: { cssSelector: string }) => {
        // Procura no main/iframes e marca o primeiro match
        const locator = await getLocator(args.cssSelector);
        const elementId = randomUUID();

        await locator.evaluate((node, id) => node.setAttribute("data-element-id", id), elementId);

        // Retorna um CSS selector para ser usado nos outros métodos
        return { elementId: createMarkedSelector(elementId) };
      },
      name: "locateElement",
      description:
        "Locates element using a CSS selector and returns a CSS selector (data-element-id) to be used with other functions.",
      parse: (args: string) => z.object({ cssSelector: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { cssSelector: { type: "string" } } },
    },

    locator_evaluate: {
      function: async (args: { pageFunction: string; elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { result: await locator.evaluate(args.pageFunction as any) };
      },
      description: "Execute JavaScript code in the page, taking the matching element as an argument.",
      name: "locator_evaluate",
      parameters: {
        type: "object",
        properties: {
          elementId: { type: "string", description: "CSS selector for the element." },
          pageFunction: {
            type: "string",
            description: "Function to be evaluated in the page context, e.g. node => node.innerText",
          },
        },
      },
      parse: (args: string) =>
        z.object({ elementId: z.string(), pageFunction: z.string() }).parse(JSON.parse(args)),
    },

    locator_getAttribute: {
      function: async (args: { attributeName: string; elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { attributeValue: await locator.getAttribute(args.attributeName) };
      },
      name: "locator_getAttribute",
      description: "Returns the matching element's attribute value.",
      parse: (args: string) =>
        z.object({ elementId: z.string(), attributeName: z.string() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: { attributeName: { type: "string" }, elementId: { type: "string" } },
      },
    },

    locator_innerHTML: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { innerHTML: await locator.innerHTML() };
      },
      name: "locator_innerHTML",
      description: "Returns the element.innerHTML.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_innerText: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { innerText: await locator.innerText() };
      },
      name: "locator_innerText",
      description: "Returns the element.innerText.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_textContent: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { textContent: await locator.textContent() };
      },
      name: "locator_textContent",
      description: "Returns the node.textContent.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_inputValue: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { inputValue: await locator.inputValue() };
      },
      name: "locator_inputValue",
      description: "Returns input.value for the selected <input>/<textarea>/<select>.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_blur: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        await locator.blur();
        return { success: true };
      },
      name: "locator_blur",
      description: "Removes keyboard focus from the current element.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_boundingBox: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return await locator.boundingBox();
      },
      name: "locator_boundingBox",
      description:
        "Returns the bounding box of the element matching the locator, or null if not visible.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_check: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        await locator.check({ timeout: 10000 });
        return { success: true };
      },
      name: "locator_check",
      description: "Ensure that checkbox or radio element is checked.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_uncheck: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        await locator.uncheck({ timeout: 10000 });
        return { success: true };
      },
      name: "locator_uncheck",
      description: "Ensure that checkbox or radio element is unchecked.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_isChecked: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { isChecked: await locator.isChecked() };
      },
      name: "locator_isChecked",
      description: "Returns whether the element is checked.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_isEditable: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { isEditable: await locator.isEditable() };
      },
      name: "locator_isEditable",
      description: "Returns whether the element is editable (enabled + not readonly).",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_isEnabled: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { isEnabled: await locator.isEnabled() };
      },
      name: "locator_isEnabled",
      description: "Returns whether the element is enabled.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_isVisible: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { isVisible: await locator.isVisible() };
      },
      name: "locator_isVisible",
      description: "Returns whether the element is visible.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_clear: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        await locator.clear({ timeout: 10000 });
        return { success: true };
      },
      name: "locator_clear",
      description: "Clear the input field.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_click: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        await robustClick(locator);
        return { success: true };
      },
      name: "locator_click",
      description: "Click an element.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_count: {
      function: async (args: { elementId: string }) => {
        const locator = await getLocator(args.elementId);
        return { elementCount: await locator.count() };
      },
      name: "locator_count",
      description: "Returns the number of elements matching the locator.",
      parse: (args: string) => z.object({ elementId: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { elementId: { type: "string" } } },
    },

    locator_fill: {
      function: async (args: { value: string; elementId: string }) => {
        const locator = await getLocator(args.elementId);
        await robustFill(locator, args.value);
        return { success: true };
      },
      name: "locator_fill",
      description: "Set a value to the input field.",
      parse: (args: string) =>
        z.object({ elementId: z.string(), value: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { value: { type: "string" }, elementId: { type: "string" } } },
    },

    page_goto: {
      function: async (args: { url: string }) => ({ url: await page.goto(args.url) }),
      name: "page_goto",
      description: "Navigate to the specified URL.",
      parse: (args: string) => z.object({ url: z.string() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: { url: { type: "string", description: "The URL to navigate to" } },
        required: ["url"],
      },
    },

    locator_selectOption: {
      function: async (args: {
        elementId?: string;   // agora é CSS selector também
        cssSelector?: string; // idem
        value?: string | string[];
        label?: string | string[];
        index?: number | number[];
      }) => {
        const { elementId, cssSelector, value, label, index } = args;

        const selector = elementId ?? cssSelector;
        if (!selector) throw new Error("You must provide either elementId or cssSelector.");

        const locator = await getLocator(selector);

        if (value !== undefined) {
          await locator.selectOption(value);
        } else if (label !== undefined) {
          const options = Array.isArray(label) ? label.map((l) => ({ label: l })) : { label };
          await locator.selectOption(options);
        } else if (index !== undefined) {
          const options = Array.isArray(index) ? index.map((i) => ({ index: i })) : { index };
          await locator.selectOption(options);
        } else {
          throw new Error("You must provide at least one of: value, label, or index.");
        }

        return { success: true };
      },
      name: "locator_selectOption",
      description: "Selects option(s) in a <select> element (CSS selector; works in iframes).",
      parse: (args: string) => {
        return z
          .object({
            elementId: z.string().optional(),
            cssSelector: z.string().optional(),
            value: z.union([z.string(), z.array(z.string())]).optional(),
            label: z.union([z.string(), z.array(z.string())]).optional(),
            index: z.union([z.number(), z.array(z.number())]).optional(),
          })
          .refine((d) => d.elementId !== undefined || d.cssSelector !== undefined, {
            message: "Either elementId or cssSelector must be provided.",
          })
          .refine((d) => d.value !== undefined || d.label !== undefined || d.index !== undefined, {
            message: "At least one of value, label, or index must be provided.",
          })
          .parse(JSON.parse(args));
      },
      parameters: {
        type: "object",
        properties: {
          elementId: { type: "string", description: "CSS selector for the <select> element." },
          cssSelector: { type: "string", description: "CSS selector for the <select> element." },
          value: { type: ["string", "array"], items: { type: "string" } },
          label: { type: ["string", "array"], items: { type: "string" } },
          index: { type: ["number", "array"], items: { type: "number" } },
        },
      },
    },

    expect_toBe: {
      function: (args: { actual: string; expected: string }) => ({
        actual: args.actual,
        expected: args.expected,
        success: args.actual === args.expected,
      }),
      name: "expect_toBe",
      description: "Asserts that the actual value is equal to the expected value.",
      parse: (args: string) => z.object({ actual: z.string(), expected: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { actual: { type: "string" }, expected: { type: "string" } } },
    },

    expect_notToBe: {
      function: (args: { actual: string; expected: string }) => ({
        actual: args.actual,
        expected: args.expected,
        success: args.actual !== args.expected,
      }),
      name: "expect_notToBe",
      description: "Asserts that the actual value is not equal to the expected value.",
      parse: (args: string) => z.object({ actual: z.string(), expected: z.string() }).parse(JSON.parse(args)),
      parameters: { type: "object", properties: { actual: { type: "string" }, expected: { type: "string" } } },
    },

    resultAssertion: {
      function: (args: { assertion: boolean }) => args,
      parse: (args: string) => z.object({ assertion: z.boolean() }).parse(JSON.parse(args)),
      description: "Called at the end when the initial instructions asked to assert something.",
      name: "resultAssertion",
      parameters: { type: "object", properties: { assertion: { type: "boolean" } } },
    },

    resultQuery: {
      function: (args: { query: string }) => args,
      parse: (args: string) => z.object({ query: z.string() }).parse(JSON.parse(args)),
      description: "Called at the end when the initial instructions asked to extract data.",
      name: "resultQuery",
      parameters: { type: "object", properties: { query: { type: "string" } } },
    },

    resultAction: {
      function: () => ({ success: true }),
      parse: (args: string) => z.object({}).parse(JSON.parse(args)),
      description: "Called at the end when the initial instructions asked to perform an action.",
      name: "resultAction",
      parameters: { type: "object", properties: {} },
    },

    resultError: {
      function: (args: { errorMessage: string }) => ({ errorMessage: args.errorMessage }),
      parse: (args: string) => z.object({ errorMessage: z.string() }).parse(JSON.parse(args)),
      description: "If user instructions cannot be completed, produces the final response.",
      name: "resultError",
      parameters: { type: "object", properties: { errorMessage: { type: "string" } } },
    },

    getVisibleStructure: {
      function: async () => {
        const sanitizeOptions = getSanitizeOptions();
        const allowedTags = sanitizeOptions.allowedTags || [];
        const allowedAttributes = sanitizeOptions.allowedAttributes;
        const maxDepth = 30;

        return {
          structure: await page.evaluate(({ allowedTags, allowedAttributes, maxDepth }) => {
            // @ts-ignore
            const extractVisibleStructure = (element, depth = 0) => {
              if (!element || depth > maxDepth) return null;

              const style = window.getComputedStyle(element);
              if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") {
                return null;
              }

              const tag = element.tagName.toLowerCase();
              if (!allowedTags.includes(tag)) return null;

              const node: any = { tag, attributes: {}, children: [] };

              const elementAttributes = element.attributes;
              if (allowedAttributes === false) {
                for (let i = 0; i < elementAttributes.length; i++) {
                  const attr = elementAttributes[i];
                  node.attributes[attr.name] = attr.value;
                }
              } else if (typeof allowedAttributes === "object") {
                const allowedForAll: any = (allowedAttributes as any)["*"];
                const allowedForTag: any = (allowedAttributes as any)[tag];

                const allowAllForTag = allowedForTag === true;
                const allowAllGlobal = allowedForAll === true;

                for (let i = 0; i < elementAttributes.length; i++) {
                  const attr = elementAttributes[i];
                  const attrName = attr.name;

                  if (
                    allowAllForTag ||
                    allowAllGlobal ||
                    (Array.isArray(allowedForTag) && allowedForTag.includes(attrName)) ||
                    (Array.isArray(allowedForAll) && allowedForAll.includes(attrName))
                  ) {
                    node.attributes[attrName] = attr.value;
                  }
                }
              }

              if (element.id) node.id = element.id;

              const role = element.getAttribute("role");
              if (role) node.role = role;

              const ariaLabel = element.getAttribute("aria-label");
              if (ariaLabel) node.ariaLabel = ariaLabel;

              const className = (element.className || "").trim();
              if (className) node.className = className;

              if (element.childNodes.length === 1 && element.childNodes[0].nodeType === 3) {
                const text = (element.textContent || "").trim();
                if (text) node.text = text.length > 50 ? text.slice(0, 50) + "..." : text;
              }

              if (depth + 1 < maxDepth) {
                for (let i = 0; i < element.children.length; i++) {
                  const child = extractVisibleStructure(element.children[i], depth + 1);
                  if (child) node.children.push(child);
                }
              }

              return node;
            };

            return extractVisibleStructure(document.body);
          }, { allowedTags, allowedAttributes, maxDepth }),
        };
      },
      name: "getVisibleStructure",
      description: "Returns a simplified hierarchical structure of visible DOM elements.",
      parse: (args: string) => z.object({}).parse(JSON.parse(args)),
      parameters: { type: "object", properties: {} },
    },

    locateElementsByRole: {
      function: async (args: { role: any; exact?: boolean }) => {
        // OBS: getByRole não atravessa iframes automaticamente.
        // Mantemos comportamento atual para main frame; se precisar em iframes, use cssSelector direto.
        const locators = await page.getByRole(args.role, { exact: args.exact ?? false }).all();
        const elementIds: string[] = [];

        for (const loc of locators) {
          const id = randomUUID();
          await loc.evaluate((node, _id) => node.setAttribute("data-element-id", _id), id);
          elementIds.push(createMarkedSelector(id));
        }

        return { elementIds, count: elementIds.length };
      },
      name: "locateElementsByRole",
      description: "Finds elements by role and returns array of CSS selectors (data-element-id).",
      parse: (args: string) => z.object({ role: z.string(), exact: z.boolean().optional() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          role: { type: "string", description: "ARIA role to search for." },
          exact: { type: "boolean", description: "Whether to match exactly." },
        },
        required: ["role"],
      },
    },

    locateElementsWithText: {
      function: async (args: { text: string; exact?: boolean }) => {
        // Mantém comportamento atual no main frame
        const allLocators = await page.getByText(args.text, { exact: args.exact ?? false }).all();
        const elementIds: string[] = [];

        for (const loc of allLocators) {
          if (await loc.isVisible()) {
            const id = randomUUID();
            await loc.evaluate((node, _id) => node.setAttribute("data-element-id", _id), id);
            elementIds.push(createMarkedSelector(id));
          }
        }

        return { elementIds, count: elementIds.length };
      },
      name: "locateElementsWithText",
      description: "Finds visible elements containing text and returns array of CSS selectors (data-element-id).",
      parse: (args: string) => z.object({ text: z.string(), exact: z.boolean().optional() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          text: { type: "string", description: "Text to search for within elements." },
          exact: { type: "boolean", description: "Whether to match exactly." },
        },
        required: ["text"],
      },
    },

    waitForContentToLoad: {
      function: async (args: { selector: string; textMarker?: string; timeout?: number }) => {
        try {
          const sel = normalizeSelector(args.selector);
          if (args.textMarker) {
            await page.waitForSelector(`${sel}:has-text("${args.textMarker}")`, {
              timeout: args.timeout || 30000,
              state: "visible",
            });
          } else {
            await page.waitForSelector(sel, { timeout: args.timeout || 30000, state: "visible" });
          }
          return { success: true };
        } catch (error: any) {
          return { success: false, error: `Timeout waiting for content to load: ${error.message}` };
        }
      },
      name: "waitForContentToLoad",
      description: "Waits for dynamic content to load based on selector and optional text marker.",
      parse: (args: string) =>
        z.object({ selector: z.string(), textMarker: z.string().optional(), timeout: z.number().optional() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          selector: { type: "string", description: "CSS selector to wait for." },
          textMarker: { type: "string", description: "Optional text content marker." },
          timeout: { type: "number", description: "Max wait time in ms (default 30000)." },
        },
        required: ["selector"],
      },
    },

    extractVisibleText: {
      function: async (args: { elementId?: string; selector?: string }) => {
        let result: any;

        if (args.elementId) {
          const loc = await getLocator(args.elementId);
          result = await loc.evaluate((node: Element) => {
            const getVisibleText = (element: Element | Node): string => {
              if (element.nodeType === 3) return element.textContent?.trim() || "";

              if (element instanceof Element) {
                const style = window.getComputedStyle(element);
                if (style.display === "none" || style.visibility === "hidden" || style.opacity === "0") return "";

                let text = "";
                Array.from(element.childNodes).forEach((child) => (text += getVisibleText(child)));
                return text;
              }

              return "";
            };

            return getVisibleText(node);
          });
        } else if (args.selector) {
          // selector (CSS) somente no main doc (mantém seu comportamento)
          result = await page.evaluate((selector: string) => {
            const elements = document.querySelectorAll(selector);
            let allText = "";
            elements.forEach((element) => {
              const style = window.getComputedStyle(element);
              if (style.display !== "none" && style.visibility !== "hidden" && style.opacity !== "0") {
                allText += (element.textContent?.trim() || "") + " ";
              }
            });
            return allText.trim();
          }, args.selector);
        } else {
          throw new Error("Either elementId or selector must be provided");
        }

        return { text: result };
      },
      name: "extractVisibleText",
      description: "Extracts only visible text from elements, ignoring hidden content.",
      parse: (args: string) =>
        z.object({ elementId: z.string().optional(), selector: z.string().optional() })
          .refine((d) => d.elementId !== undefined || d.selector !== undefined, { message: "Either elementId or selector must be provided" })
          .parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          elementId: { type: "string", description: "CSS selector for the element to extract text from." },
          selector: { type: "string", description: "CSS selector to locate elements for text extraction." },
        },
      },
    },

    scrollIntoElementView: {
      function: async (args: { elementId: string; behavior?: string }) => {
        const loc = await getLocator(args.elementId);
        await loc.evaluate((node: Element, behavior: string | undefined) => {
          node.scrollIntoView({
            behavior: (behavior as "auto" | "smooth") || "smooth",
            block: "center",
          });
        }, args.behavior);

        await page.waitForTimeout(500);
        return { success: true };
      },
      name: "scrollIntoElementView",
      description: "Scrolls to bring an element into view.",
      parse: (args: string) =>
        z.object({ elementId: z.string(), behavior: z.enum(["auto", "smooth"]).optional() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          elementId: { type: "string", description: "CSS selector for the element." },
          behavior: { type: "string", enum: ["auto", "smooth"] as any, description: "Scrolling behavior." },
        },
        required: ["elementId"],
      },
    },

    waitForNetworkIdle: {
      function: async (args: { timeout?: number; idleTime?: number }) => {
        try {
          await page.waitForLoadState("networkidle", { timeout: args.timeout || 30000 });
          if (args.idleTime) await page.waitForTimeout(args.idleTime);
          return { success: true };
        } catch (error: any) {
          return { success: false, error: `Timeout waiting for network idle: ${error.message}` };
        }
      },
      name: "waitForNetworkIdle",
      description: "Waits for network activity to be minimal or stopped.",
      parse: (args: string) => z.object({ timeout: z.number().optional(), idleTime: z.number().optional() }).parse(JSON.parse(args)),
      parameters: {
        type: "object",
        properties: {
          timeout: { type: "number", description: "Max wait time in ms (default 30000)." },
          idleTime: { type: "number", description: "Extra wait time after idle (ms)." },
        },
      },
    },
  };
};
