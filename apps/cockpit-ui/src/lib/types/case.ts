// Re-export of the generated Case + CaseEnvelope + CaseState types so cockpit
// components import from a stable, ergonomic path. Story 2.3 / Subtask 1.2.

import type { components } from '@/api-types';

export type Case = components['schemas']['CaseEnvelope'];
export type CaseEnvelope = components['schemas']['CaseEnvelope'];
export type CaseState = components['schemas']['CaseState'];
export type CustomerMetadata = components['schemas']['CustomerMetadata'];
