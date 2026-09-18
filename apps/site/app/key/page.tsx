import { Redirect } from '@/components/pages/Redirect'

/** Replaced by `/account`, where the key, the payments and the tickets all live. */
export default function MovedPage() {
  return <Redirect to="/account" />
}
