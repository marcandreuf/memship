import "./commands";
import registerCypressGrep from "@cypress/grep";

registerCypressGrep();

// Set locale to English for all tests
beforeEach(() => {
  cy.setCookie("NEXT_LOCALE", "en");
});
