"""
curriculum.py — helper functions for the module/curriculum system.
"""
from models import db, Module, ModuleExercise, SectionModuleExercise, ModuleCompletion


def effective_exercises(section, module):
    """
    Return the effective list of exercises for `module` in `section`,
    applying SectionModuleExercise overrides.

    Returns a list of dicts:
      {
        'source': 'course' | 'section',
        'module_exercise_id': int | None,
        'section_exercise_id': int | None,
        'exercise_type': str,
        'exercise_id': int,
        'order': int,
        'completion_criterion': dict,
      }
    """
    removed_ids   = set()
    overrides     = {}  # module_exercise_id -> SectionModuleExercise
    additions     = []
    module_hidden = False

    for sme in SectionModuleExercise.query.filter_by(section_id=section.id).all():
        if sme.action == 'hide' and sme.module_exercise_id is None:
            # Module-level hide: one row, module_exercise_id NULL.
            if sme.module_id == module.id:
                module_hidden = True
        elif sme.action == 'hide' and sme.module_exercise_id:
            # Exercise-level hide, independent of any module-level hide.
            removed_ids.add(sme.module_exercise_id)
        elif sme.action == 'remove' and sme.module_exercise_id:
            removed_ids.add(sme.module_exercise_id)
        elif sme.action == 'override' and sme.module_exercise_id:
            overrides[sme.module_exercise_id] = sme
        elif sme.action == 'add' and sme.module_id == module.id:
            additions.append(sme)

    if module_hidden:
        return []

    result = []
    for me in module.exercises.order_by(ModuleExercise.order).all():
        if me.id in removed_ids:
            continue
        if me.id in overrides:
            sme = overrides[me.id]
            result.append({
                'source': 'section',
                'module_exercise_id': me.id,
                'section_exercise_id': sme.id,
                'exercise_type': sme.exercise_type or me.exercise_type,
                'exercise_id': sme.exercise_id or me.exercise_id,
                'order': sme.order if sme.order is not None else me.order,
                'completion_criterion': sme.completion_criterion or me.completion_criterion,
            })
        else:
            result.append({
                'source': 'course',
                'module_exercise_id': me.id,
                'section_exercise_id': None,
                'exercise_type': me.exercise_type,
                'exercise_id': me.exercise_id,
                'order': me.order,
                'completion_criterion': me.completion_criterion,
            })

    for sme in additions:
        result.append({
            'source': 'section',
            'module_exercise_id': None,
            'section_exercise_id': sme.id,
            'exercise_type': sme.exercise_type,
            'exercise_id': sme.exercise_id,
            'order': sme.order or 9999,
            'completion_criterion': sme.completion_criterion or {'attempts': 1},
        })

    result.sort(key=lambda x: x['order'])
    return result


def is_module_hidden(section, module_id):
    """True if `module_id` has a module-level hide row (module_exercise_id
    NULL) for this section. Used by the student launcher routes to 404 on
    hidden work instead of relying on callers to notice an empty list."""
    return SectionModuleExercise.query.filter_by(
        section_id=section.id, module_id=module_id,
        module_exercise_id=None, action='hide'
    ).first() is not None


def is_exercise_hidden(section, module_exercise_id):
    """True if this specific module_exercise_id has an exercise-level hide
    row for this section — independent of whether its module is hidden."""
    return SectionModuleExercise.query.filter_by(
        section_id=section.id, module_exercise_id=module_exercise_id,
        action='hide'
    ).first() is not None


def get_completion(user_id, section_id, module_exercise_id=None, section_exercise_id=None):
    """Return ModuleCompletion or None."""
    q = ModuleCompletion.query.filter_by(user_id=user_id, section_id=section_id)
    if module_exercise_id is not None:
        q = q.filter_by(module_exercise_id=module_exercise_id)
    if section_exercise_id is not None:
        q = q.filter_by(section_exercise_id=section_exercise_id)
    return q.first()


def record_attempt(user_id, section_id, module_exercise_id=None, section_exercise_id=None,
                   score=None, criterion=None):
    """
    Record one attempt toward a module exercise. Increments counters and marks complete
    when criterion is met. Returns (ModuleCompletion, just_completed: bool).
    """
    if criterion is None:
        criterion = {'attempts': 1}

    mc = get_completion(user_id, section_id, module_exercise_id, section_exercise_id)
    if mc is None:
        mc = ModuleCompletion(
            user_id=user_id,
            section_id=section_id,
            module_exercise_id=module_exercise_id,
            section_exercise_id=section_exercise_id,
            attempt_count=0,
            passing_count=0,
            is_complete=False,
            best_score=None,
        )
        db.session.add(mc)

    was_complete = mc.is_complete
    mc.attempt_count += 1

    if score is not None:
        if mc.best_score is None or score > mc.best_score:
            mc.best_score = score
        min_score = criterion.get('min_score', 70)
        if score >= min_score:
            mc.passing_count += 1

    if not was_complete:
        required_attempts = criterion.get('attempts')
        required_passing  = criterion.get('passing')
        if required_attempts is not None and mc.attempt_count >= required_attempts:
            mc.is_complete = True
        elif required_passing is not None and mc.passing_count >= required_passing:
            mc.is_complete = True

    db.session.commit()
    return mc, (mc.is_complete and not was_complete)


def completion_map(user_id, section_id):
    """
    Return a set of (module_exercise_id, section_exercise_id) tuples that are
    fully complete (is_complete=True) for this user in this section.
    """
    completions = ModuleCompletion.query.filter_by(
        user_id=user_id, section_id=section_id, is_complete=True
    ).all()
    return {(c.module_exercise_id, c.section_exercise_id) for c in completions}


def get_progress(user_id, section_id, module_exercise_id=None, section_exercise_id=None,
                 criterion=None):
    """
    Return progress dict: {'count': int, 'required': int, 'complete': bool}.
    'count' is attempts or passing_count depending on criterion type.
    """
    if criterion is None:
        criterion = {'attempts': 1}

    mc = get_completion(user_id, section_id, module_exercise_id, section_exercise_id)
    if mc is None:
        count = 0
    elif 'passing' in criterion:
        count = mc.passing_count
    else:
        count = mc.attempt_count

    required = criterion.get('attempts') or criterion.get('passing') or 1
    complete = mc.is_complete if mc else False
    return {'count': count, 'required': required, 'complete': complete}


def next_incomplete(user_id, section_id, section, module):
    """
    Return the first exercise dict (from effective_exercises) in `module` that is not
    yet completed for this user in this section. Returns None if all are done.
    """
    done = completion_map(user_id, section_id)
    for ex in effective_exercises(section, module):
        key = (ex['module_exercise_id'], ex['section_exercise_id'])
        if key not in done:
            return ex
    return None


def modules_with_progress(user_id, section_id, section):
    """
    For each module in the section's course, return:
      {'module': Module, 'total': int, 'completed': int, 'exercises': list}
    Returns [] if the section has no course.
    """
    if not section.course_id:
        return []
    result = []
    done = completion_map(user_id, section_id)
    hidden_module_ids = {
        sme.module_id for sme in
        SectionModuleExercise.query.filter_by(section_id=section.id, action='hide').all()
        if sme.module_exercise_id is None and sme.module_id is not None
    }
    for module in section.course.modules.order_by(Module.order).all():
        if module.id in hidden_module_ids:
            continue
        exs = effective_exercises(section, module)
        completed_count = sum(
            1 for ex in exs
            if (ex['module_exercise_id'], ex['section_exercise_id']) in done
        )
        result.append({
            'module': module,
            'total': len(exs),
            'completed': completed_count,
            'exercises': exs,
        })
    return result
