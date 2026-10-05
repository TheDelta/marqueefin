// The coverage report of all tests (coverage.mjs); fails the run below its minimum
import { coverage } from "./coverage.mjs";

export default async function globalTeardown() {
  await coverage().generate();
}
